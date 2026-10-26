from types import SimpleNamespace

import pandas as pd
import pytest

from app.services import tickers


def test_candidates_order_for_bare_symbol() -> None:
    assert tickers.candidates("infy") == ["INFY.NS", "INFY.BO", "INFY"]


@pytest.mark.parametrize("sym", ["TCS.NS", "tcs.ns", "500325.BO"])
def test_existing_suffix_is_kept(sym: str) -> None:
    assert tickers.candidates(sym) == [sym.upper()]


def test_candidates_strip_unsafe_characters() -> None:
    assert tickers.candidates(" ab c;$ ") == ["ABC.NS", "ABC.BO", "ABC"]
    assert tickers.candidates("  ;; ") == []


def test_prefers_ns_then_bo_then_plain() -> None:
    avail = {"A.NS", "B.BO", "C"}
    resolved, unresolved = tickers.resolve_symbols(
        ["A", "B", "C", "ZZZ"], exists=avail.__contains__
    )
    assert resolved == {"A": "A.NS", "B": "B.BO", "C": "C"}
    assert unresolved == ["ZZZ"]


def test_both_exchanges_available_picks_ns() -> None:
    resolved, _ = tickers.resolve_symbols(["X"], exists=lambda t: t in {"X.NS", "X.BO", "X"})
    assert resolved["X"] == "X.NS"


def test_explicit_suffix_not_retried_on_other_exchange() -> None:
    calls: list[str] = []

    def exists(t: str) -> bool:
        calls.append(t)
        return False

    _, unresolved = tickers.resolve_symbols(["TCS.NS"], exists=exists)
    assert unresolved == ["TCS.NS"]
    assert calls == ["TCS.NS"]


def test_has_data_uses_yfinance_history(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = {"GOOD": pd.DataFrame({"Close": [1.0]}), "EMPTY": pd.DataFrame()}

    def fake_ticker(t: str) -> SimpleNamespace:
        if t == "BOOM":
            raise RuntimeError("network down")
        return SimpleNamespace(history=lambda **_: frames[t])

    monkeypatch.setattr(tickers.yf, "Ticker", fake_ticker)
    assert tickers._has_data("GOOD") is True
    assert tickers._has_data("EMPTY") is False
    assert tickers._has_data("BOOM") is False
