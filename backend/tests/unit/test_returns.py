import numpy as np
import pandas as pd
import pytest

from app.analytics import returns as ret


def idx(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="B")


def test_daily_returns_hand_calculated() -> None:
    values = pd.Series([100.0, 110.0, 99.0, 120.0], index=idx(4))
    r = ret.daily_returns(values)
    assert r.tolist() == pytest.approx([0.10, -0.10, 120 / 99 - 1], abs=1e-12)
    assert len(r) == 3


def test_portfolio_value_sums_quantity_times_price() -> None:
    prices = pd.DataFrame({"A": [10.0, 12.0], "B": [100.0, 90.0]}, index=idx(2))
    v = ret.portfolio_value(prices, pd.Series({"A": 2, "B": 1}))
    assert v.tolist() == [120.0, 114.0]


def test_to_base_currency_same_currency_is_identity() -> None:
    s = pd.Series([1.0, 2.0], index=idx(2))
    assert ret.to_base_currency(s, "INR", "INR", None) is s


def test_to_base_currency_usd_to_inr_multiplies() -> None:
    s = pd.Series([10.0, 20.0], index=idx(2))
    fx = pd.Series([80.0, 82.0], index=idx(2))
    assert ret.to_base_currency(s, "USD", "INR", fx).tolist() == [800.0, 1640.0]


def test_to_base_currency_inr_to_usd_divides() -> None:
    s = pd.Series([800.0, 1640.0], index=idx(2))
    fx = pd.Series([80.0, 82.0], index=idx(2))
    assert ret.to_base_currency(s, "INR", "USD", fx).tolist() == [10.0, 20.0]


def test_to_base_currency_forward_fills_fx_on_missing_day() -> None:
    s = pd.Series([10.0, 10.0, 10.0], index=idx(3))
    fx = pd.Series([80.0, 90.0], index=[s.index[0], s.index[2]])
    out = ret.to_base_currency(s, "USD", "INR", fx)
    assert out.tolist() == [800.0, 800.0, 900.0]


def test_to_base_currency_requires_fx() -> None:
    with pytest.raises(ValueError):
        ret.to_base_currency(pd.Series([1.0]), "USD", "INR", None)


def test_clean_prices_drops_short_history_and_fills_small_gaps() -> None:
    n = 70
    full = pd.Series(np.arange(n, dtype=float) + 1, index=idx(n))
    gap = full.copy()
    gap.iloc[10:13] = np.nan
    short = full.copy()
    short.iloc[:20] = np.nan
    short.iloc[20:] = full.iloc[20:]
    df = pd.DataFrame({"full": full, "gap": gap, "short": short})
    cleaned, dropped = ret.clean_prices(df, min_days=60, max_ffill_days=5)
    assert dropped == ["short"]
    assert cleaned["gap"].iloc[11] == full.iloc[9]  # forward-filled
    assert len(cleaned) == n


def test_clean_prices_does_not_fill_gaps_longer_than_limit() -> None:
    n = 70
    s = pd.Series(np.arange(n, dtype=float) + 1, index=idx(n))
    s.iloc[10:20] = np.nan
    cleaned, _ = ret.clean_prices(pd.DataFrame({"x": s}), min_days=60, max_ffill_days=5)
    assert len(cleaned) < n
