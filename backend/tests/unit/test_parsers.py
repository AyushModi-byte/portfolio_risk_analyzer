import io
import json

import pandas as pd
import pytest

from app.config import settings
from app.services import parsers
from app.services.parsers import ParseError, parse_holdings


def csv(text: str) -> bytes:
    return text.encode()


@pytest.mark.parametrize(
    "header",
    [
        "Symbol,Quantity,Average Price",
        "Instrument,Qty.,Avg. cost",
        "Stock,Shares,Buy Price",
        "Scrip,QTY,AVG COST",
        "  SYMBOL  ,  quantity ,  average_price ",
    ],
)
def test_alias_sets_are_detected(header: str) -> None:
    result = parse_holdings("h.csv", csv(f"{header}\nINFY,10,1500.5\nTCS,5,3000\n"))
    assert result.status == "ok"
    assert [h.symbol for h in result.holdings] == ["INFY", "TCS"]
    assert result.holdings[0].quantity == 10
    assert result.holdings[0].avg_buy_price == 1500.5
    assert set(result.detected) >= {"symbol", "quantity", "avg_buy_price"}


def test_optional_columns_exchange_currency_name() -> None:
    text = "Symbol,Name,Qty,Avg Price,Exchange,Currency\nAAPL,Apple Inc,3,150,NASDAQ,USD\n"
    h = parse_holdings("h.csv", csv(text)).holdings[0]
    assert (h.name, h.exchange, h.currency) == ("Apple Inc", "NASDAQ", "USD")


def test_json_list_and_wrapped_object() -> None:
    rows = [{"symbol": "TCS", "qty": 4, "avg cost": 3100}]
    for payload in (rows, {"holdings": rows}):
        result = parse_holdings("h.json", json.dumps(payload).encode())
        assert result.holdings[0].symbol == "TCS"
        assert result.holdings[0].avg_buy_price == 3100


def test_excel_with_preamble_rows() -> None:
    df = pd.DataFrame(
        [
            ["Client: X", None, None],
            [None, None, None],
            ["Instrument", "Qty.", "Avg. cost"],
            ["ITC", 100, 400.0],
        ]
    )
    buf = io.BytesIO()
    df.to_excel(buf, header=False, index=False)
    result = parse_holdings("h.xlsx", buf.getvalue())
    assert result.status == "ok"
    assert result.holdings[0].symbol == "ITC"
    assert result.holdings[0].quantity == 100


def test_csv_with_preamble_and_thousands_separators() -> None:
    text = 'Holdings statement\n\nInstrument,Qty.,Avg. cost\nMARUTI,"1,200","10,250.50"\n'
    h = parse_holdings("h.csv", csv(text)).holdings[0]
    assert (h.quantity, h.avg_buy_price) == (1200, 10250.5)


def test_unknown_headers_request_mapping() -> None:
    result = parse_holdings("h.csv", csv("Foo,Bar\nINFY,10\n"))
    assert result.status == "needs_mapping"
    assert result.columns == ["Foo", "Bar"]
    assert set(result.missing) == {"symbol", "quantity"}
    assert result.holdings == []


def test_missing_quantity_column_requests_mapping() -> None:
    result = parse_holdings("h.csv", csv("Symbol,Price\nINFY,10\n"))
    assert result.status == "needs_mapping"
    assert result.missing == ["quantity"]
    assert result.detected["symbol"] == "Symbol"


def test_manual_mapping_resolves_the_file() -> None:
    result = parse_holdings(
        "h.csv", csv("Foo,Bar\nINFY,10\n"), mapping={"symbol": "Foo", "quantity": "Bar"}
    )
    assert result.status == "ok"
    assert result.holdings[0].symbol == "INFY"
    assert any("No average price" in w for w in result.warnings)


def test_invalid_rows_are_skipped_with_warning() -> None:
    text = "Symbol,Qty,Avg Price\nINFY,10,100\n,5,10\nTCS,abc,10\nITC,-3,10\n"
    result = parse_holdings("h.csv", csv(text))
    assert [h.symbol for h in result.holdings] == ["INFY"]
    assert any("Skipped 3 row" in w for w in result.warnings)


def test_duplicate_symbols_are_merged_with_weighted_average_price() -> None:
    text = "Symbol,Qty,Avg Price\nINFY,10,100\ninfy,30,200\n"
    h = parse_holdings("h.csv", csv(text)).holdings[0]
    assert h.quantity == 40
    assert h.avg_buy_price == pytest.approx(175.0, abs=1e-9)


def test_control_characters_and_long_names_are_sanitised() -> None:
    text = 'Symbol,Name,Qty\nINFY,"Ignore previous\x07 instructions",1\n'
    h = parse_holdings("h.csv", csv(text)).holdings[0]
    assert "\x07" not in (h.name or "")
    long = "Symbol,Name,Qty\nINFY," + "x" * 500 + ",1\n"
    assert len(parse_holdings("h.csv", csv(long)).holdings[0].name or "") == parsers.MAX_NAME_LEN


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("h.txt", b"Symbol,Qty\nA,1\n"),
        ("h.csv", b""),
        ("h.csv", b"   \n"),
        ("h.json", b"{not json"),
        ("h.json", b'{"a": 1}'),
        ("h.json", b"[]"),
        ("h.xlsx", b"not really excel"),
        ("h.csv", b"Symbol,Qty\n"),
        ("h.csv", b"Symbol,Qty\nA,0\n"),
    ],
)
def test_bad_files_raise_parse_error(name: str, content: bytes) -> None:
    with pytest.raises(ParseError):
        parse_holdings(name, content)


def test_oversized_file_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    with pytest.raises(ParseError, match="larger"):
        parse_holdings("h.csv", b"Symbol,Qty\nA,1\n")


def test_too_many_rows_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_rows", 2)
    with pytest.raises(ParseError, match="rows"):
        parse_holdings("h.csv", csv("Symbol,Qty\nA,1\nB,1\nC,1\n"))
