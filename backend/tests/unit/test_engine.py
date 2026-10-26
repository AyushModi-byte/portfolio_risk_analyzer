import numpy as np
import pandas as pd
import pytest

from app.analytics import engine
from app.config import settings
from app.schemas import DISCLAIMER, Holding


@pytest.fixture(autouse=True)
def short_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "min_history_days", 3)


def dates(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="B")


def build(
    prices: pd.DataFrame,
    quantities: dict[str, float],
    sectors: dict[str, str] | None = None,
    base: str = "INR",
    usdinr: pd.Series | None = None,
    buy: dict[str, float] | None = None,
) -> tuple[list, pd.DataFrame]:
    holdings = [
        Holding(symbol=t, quantity=q, avg_buy_price=(buy or {}).get(t))
        for t, q in quantities.items()
    ]
    tickers = {t: t + ".NS" if not t.startswith("US") else t for t in quantities}
    renamed = prices.rename(columns=tickers)
    return engine.resolve_holdings(
        holdings,
        tickers,
        {tickers[t]: s for t, s in (sectors or {}).items()},
        renamed,
        base,  # type: ignore[arg-type]
        usdinr,
    ), renamed


def test_ticker_currency() -> None:
    assert engine.ticker_currency("TCS.NS") == "INR"
    assert engine.ticker_currency("x.bo") == "INR"
    assert engine.ticker_currency("AAPL") == "USD"


def test_default_risk_free() -> None:
    assert engine.default_risk_free("INR") == 0.07
    assert engine.default_risk_free("USD") == 0.04


def test_two_equal_value_stocks_constant_prices() -> None:
    px = pd.DataFrame({"A": [100.0] * 6, "B": [50.0] * 6}, index=dates(6))
    holdings, renamed = build(px, {"A": 5, "B": 10}, {"A": "Tech", "B": "Energy"})
    bench = pd.Series([100, 101, 99, 102, 103, 104], index=dates(6), dtype=float)
    res = engine.analyze(holdings, renamed, bench, "^TEST")
    weights = {w.symbol: w.weight for w in res.weights}
    assert weights == pytest.approx({"A": 0.5, "B": 0.5}, abs=1e-6)
    assert res.risk.hhi == pytest.approx(0.5, abs=1e-6)
    assert res.risk.effective_n == pytest.approx(2.0, abs=1e-6)
    assert res.risk.volatility == 0.0
    assert res.risk.max_drawdown == 0.0
    assert res.risk.sharpe is None
    assert res.risk.beta == pytest.approx(0.0, abs=1e-9)
    assert {s.sector: s.weight for s in res.sector_exposure} == pytest.approx(
        {"Tech": 0.5, "Energy": 0.5}, abs=1e-6
    )
    assert res.disclaimer == DISCLAIMER


def test_portfolio_identical_to_benchmark_has_beta_one() -> None:
    series = pd.Series([100, 104, 99, 103, 110, 108], index=dates(6), dtype=float)
    holdings, renamed = build(pd.DataFrame({"A": series}), {"A": 3})
    res = engine.analyze(holdings, renamed, series, "^TEST")
    assert res.risk.beta == pytest.approx(1.0, abs=1e-9)
    assert res.risk.max_drawdown == pytest.approx(99 / 104 - 1, abs=1e-9)
    assert res.risk.observations == 5
    assert res.drawdown_series[0].drawdown == 0.0
    assert res.correlation.symbols == ["A"]


def test_summary_pnl_hand_calculated() -> None:
    px = pd.DataFrame({"A": [90.0, 95.0, 100.0, 100.0]}, index=dates(4))
    holdings, renamed = build(px, {"A": 10}, buy={"A": 80.0})
    res = engine.analyze(holdings, renamed, px["A"].rename("b"), "^TEST")
    assert res.summary.value == pytest.approx(1000.0, abs=1e-6)
    assert res.summary.invested == pytest.approx(800.0, abs=1e-6)
    assert res.summary.pnl == pytest.approx(200.0, abs=1e-6)
    assert res.summary.pnl_pct == pytest.approx(0.25, abs=1e-6)


def test_missing_buy_price_warns() -> None:
    px = pd.DataFrame({"A": [90.0, 95.0, 100.0, 101.0]}, index=dates(4))
    holdings, renamed = build(px, {"A": 10})
    res = engine.analyze(holdings, renamed, px["A"].rename("b"), "^TEST")
    assert res.summary.pnl_pct is None
    assert any("no buy price" in w for w in res.warnings)


def test_usd_holding_in_inr_base_uses_fx() -> None:
    px = pd.DataFrame({"US1": [10.0, 10.0, 10.0, 10.0]}, index=dates(4))
    fx = pd.Series([80.0, 80.0, 88.0, 88.0], index=dates(4))
    holdings, renamed = build(px, {"US1": 2}, base="INR", usdinr=fx)
    assert holdings[0].price_currency == "USD"
    assert holdings[0].market_value == pytest.approx(2 * 10 * 88.0, abs=1e-6)
    res = engine.analyze(holdings, renamed, px["US1"].rename("b"), "^TEST", "INR", fx)
    # value jumps 80 -> 88 on day 3: +10%
    assert res.risk.max_drawdown == 0.0
    assert res.summary.value == pytest.approx(1760.0, abs=1e-6)


def test_short_history_stock_is_dropped_with_warning() -> None:
    n = 8
    px = pd.DataFrame(
        {"A": np.linspace(100, 108, n), "B": [np.nan] * 6 + [50.0, 51.0]}, index=dates(n)
    )
    holdings, renamed = build(px, {"A": 1, "B": 1})
    res = engine.analyze(holdings, renamed, px["A"].rename("b"), "^TEST")
    assert [w.symbol for w in res.weights] == ["A"]
    assert any("Dropped B.NS" in w for w in res.warnings)


def test_not_enough_history_raises() -> None:
    px = pd.DataFrame({"A": [np.nan, np.nan, 1.0]}, index=dates(3))
    holdings, renamed = build(pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=dates(3)), {"A": 1})
    with pytest.raises(ValueError):
        engine.analyze(holdings, px.rename(columns={"A": "A.NS"}), px["A"], "^TEST")


def test_resolve_holdings_skips_unpriced_symbols() -> None:
    px = pd.DataFrame({"A.NS": [1.0, 2.0]}, index=dates(2))
    out = engine.resolve_holdings(
        [Holding(symbol="A", quantity=1), Holding(symbol="Z", quantity=1)],
        {"A": "A.NS"},
        {},
        px,
        "INR",
        None,
    )
    assert [h.symbol for h in out] == ["A"]
    assert out[0].sector == "Unknown"
