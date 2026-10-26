import numpy as np
import pandas as pd
import pytest

from app.analytics import risk

R = pd.Series([0.01, -0.02, 0.03, 0.00, -0.01], index=pd.date_range("2024-01-01", periods=5))


def test_volatility_constant_series_is_zero() -> None:
    assert risk.annualized_volatility(pd.Series([0.0] * 10)) == 0.0


def test_volatility_hand_calculated() -> None:
    # mean 0.002; squared deviations sum 0.00148 -> var 0.00037 (n-1 = 4)
    expected = np.sqrt(0.00148 / 4) * np.sqrt(252)
    assert risk.annualized_volatility(R) == pytest.approx(expected, abs=1e-12)


def test_beta_identical_series_is_one() -> None:
    assert risk.beta(R, R) == pytest.approx(1.0, abs=1e-12)


def test_beta_double_leverage_is_two() -> None:
    assert risk.beta(R * 2, R) == pytest.approx(2.0, abs=1e-12)


def test_beta_zero_variance_benchmark_is_none() -> None:
    assert risk.beta(R, pd.Series(0.0, index=R.index)) is None


def test_beta_too_few_points_is_none() -> None:
    assert risk.beta(R.iloc[:1], R.iloc[:1]) is None


def test_beta_aligns_on_common_dates() -> None:
    other = R.copy()
    other.index = other.index + pd.Timedelta(days=2)  # overlap of 3 dates
    assert risk.beta(R, other) is not None


def test_sharpe_hand_calculated() -> None:
    daily_rf = 1.04 ** (1 / 252) - 1
    expected = (0.002 - daily_rf) / np.sqrt(0.00148 / 4) * np.sqrt(252)
    assert risk.sharpe_ratio(R, 0.04) == pytest.approx(expected, abs=1e-12)


def test_sharpe_zero_vol_is_none() -> None:
    assert risk.sharpe_ratio(pd.Series([0.01] * 5), 0.04) is None


def test_var_hand_calculated() -> None:
    r = pd.Series(np.linspace(-0.10, 0.10, 21))  # 5th percentile at index 1 -> -0.09
    assert risk.historical_var(r, 0.95) == pytest.approx(0.09, abs=1e-12)


def test_var_matches_numpy_percentile() -> None:
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0, 0.01, 500))
    assert risk.historical_var(r) == pytest.approx(-np.percentile(r, 5), abs=1e-12)
