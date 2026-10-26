import pandas as pd
import pytest

from app.config import settings
from app.services import cache as cache_mod
from app.services import parsers, prices, tickers
from app.services.cache import TTLCache


def test_ttl_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    monkeypatch.setattr(cache_mod.time, "monotonic", lambda: now[0])
    c: TTLCache[int] = TTLCache(ttl_seconds=10)
    c.set("a", 1)
    assert c.get("a") == 1
    now[0] = 109.9
    assert c.get("a") == 1
    now[0] = 110.1
    assert c.get("a") is None


def test_ttl_cache_evicts_oldest_when_full() -> None:
    c: TTLCache[int] = TTLCache(ttl_seconds=60, maxsize=2)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    assert c.get("a") is None
    assert (c.get("b"), c.get("c")) == (2, 3)
    c.clear()
    assert c.get("b") is None


def test_memory_cache_serves_repeat_fetches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "offline", False)
    calls: list[str] = []
    series = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))

    def fake(ticker: str, years: int) -> pd.Series:
        calls.append(ticker)
        return series

    monkeypatch.setattr(prices, "download", fake)
    first = prices.fetch("AAA", 2)
    # remove the disk cache so only the memory cache can answer
    for f in settings.cache_dir.glob("*.csv"):
        f.unlink()
    second = prices.fetch("AAA", 2)
    assert calls == ["AAA"]
    assert second.series is not None and second.series.tolist() == [1.0, 2.0]
    assert first.live_failed is False and second.live_failed is False


def test_memory_cache_returns_copies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "offline", False)
    series = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))
    monkeypatch.setattr(prices, "download", lambda t, y: series)
    first = prices.fetch("AAA").series
    assert first is not None
    first.iloc[0] = 99.0
    again = prices.fetch("AAA").series
    assert again is not None and again.iloc[0] == 1.0


def test_fetch_many_stops_retrying_after_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "offline", False)
    tried: list[str] = []

    def fail(ticker: str, years: int) -> None:
        tried.append(ticker)

    monkeypatch.setattr(prices, "download", fail)
    df, warnings, live_failed = prices.fetch_many(["TCS.NS", "INFY.NS", "ITC.NS"])
    assert live_failed is True
    assert tried == ["TCS.NS"]
    assert list(df.columns) == ["TCS.NS", "INFY.NS", "ITC.NS"]
    assert len(warnings) == 3


def test_offline_fetch_is_not_flagged_as_live_failure() -> None:
    f = prices.fetch("TCS.NS")
    assert f.series is not None and f.warning is not None
    assert f.live_failed is False


# --- tickers: exchange hints and existence check ----------------------------------------------


@pytest.mark.parametrize(
    ("exchange", "expected"),
    [
        ("NASDAQ", ["AAPL"]),
        ("nyse", ["AAPL"]),
        ("BSE", ["AAPL.BO", "AAPL.NS", "AAPL"]),
        ("NSE", ["AAPL.NS", "AAPL.BO", "AAPL"]),
        (None, ["AAPL.NS", "AAPL.BO", "AAPL"]),
    ],
)
def test_exchange_hint_orders_candidates(exchange: str | None, expected: list[str]) -> None:
    assert tickers.candidates("AAPL", exchange) == expected


def test_resolve_uses_exchange_hint() -> None:
    seen: list[str] = []

    def exists(t: str) -> bool:
        seen.append(t)
        return True

    resolved, _ = tickers.resolve_symbols(["V"], exists=exists, exchanges={"V": "NYSE"})
    assert resolved == {"V": "V"}
    assert seen == ["V"]


def test_default_exists_uses_snapshot_offline_and_cache_online(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert tickers.default_exists("TCS.NS") is True
    assert tickers.default_exists("NOSUCH.NS") is False
    monkeypatch.setattr(settings, "offline", False)
    calls: list[str] = []

    def fake_has_data(t: str) -> bool:
        calls.append(t)
        return t == "LIVEONLY"

    monkeypatch.setattr(tickers, "_has_data", fake_has_data)
    tickers._exists_cache.clear()
    assert tickers.default_exists("LIVEONLY") is True
    assert tickers.default_exists("LIVEONLY") is True
    assert tickers.default_exists("OTHER") is False
    assert calls == ["LIVEONLY", "OTHER"]
    tickers._exists_cache.clear()


# --- parser additions -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "status"),
    [("h.xlsm", 415), ("h.xls", 415), ("h.pdf", 415), ("noextension", 415), ("h.csv", 400)],
)
def test_parse_error_status_codes(name: str, status: int) -> None:
    with pytest.raises(parsers.ParseError) as err:
        parsers.parse_holdings(name, b"" if name == "h.csv" else b"data")
    assert err.value.status_code == status


def test_broker_detection() -> None:
    assert parsers.detect_broker(["Instrument", "Qty.", "Avg. cost", "LTP"]) == "Zerodha"
    assert parsers.detect_broker(["Stock Name", "Quantity", "Average buy price"]) == "Groww"
    assert parsers.detect_broker(["Symbol", "Qty"]) is None
