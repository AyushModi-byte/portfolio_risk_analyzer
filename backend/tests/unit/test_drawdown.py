import pandas as pd
import pytest

from app.analytics import drawdown as dd


def series(*values: float) -> pd.Series:
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values)))


def test_max_drawdown_100_110_99_120() -> None:
    assert dd.max_drawdown(series(100, 110, 99, 120)) == pytest.approx(99 / 110 - 1, abs=1e-6)
    assert dd.max_drawdown(series(100, 110, 99, 120)) == pytest.approx(-0.10, abs=1e-6)


def test_constant_series_has_zero_drawdown() -> None:
    s = series(50, 50, 50, 50)
    assert dd.max_drawdown(s) == 0.0
    assert (dd.drawdown_series(s) == 0).all()


def test_double_then_halve_is_minus_fifty_percent() -> None:
    assert dd.max_drawdown(series(100, 200, 100)) == pytest.approx(-0.5, abs=1e-6)


def test_drawdown_series_values_and_recovery() -> None:
    d = dd.drawdown_series(series(100, 110, 99, 120))
    assert d.tolist() == pytest.approx([0.0, 0.0, -0.10, 0.0], abs=1e-12)


def test_monotonic_rise_never_draws_down() -> None:
    assert dd.max_drawdown(series(1, 2, 3, 4)) == 0.0


def test_drawdown_periods_closed_and_open_episodes() -> None:
    s = series(100, 110, 99, 120, 90, 100)
    eps = dd.drawdown_periods(s, n=5)
    assert len(eps) == 2
    deepest, shallow = eps
    assert deepest["depth"] == pytest.approx(90 / 120 - 1, abs=1e-9)
    assert deepest["peak_date"] == "2024-01-04"
    assert deepest["trough_date"] == "2024-01-05"
    assert deepest["recovery_date"] is None
    assert deepest["days_to_recover"] is None
    assert shallow["depth"] == pytest.approx(-0.10, abs=1e-9)
    assert shallow["peak_date"] == "2024-01-02"
    assert shallow["recovery_date"] == "2024-01-04"
    assert shallow["days_peak_to_trough"] == 1
    assert shallow["days_to_recover"] == 1


def test_drawdown_periods_limit_and_none() -> None:
    assert dd.drawdown_periods(series(1, 2, 3)) == []
    assert len(dd.drawdown_periods(series(100, 110, 99, 120, 90, 100), n=1)) == 1


def test_episodes_from_drawdown_matches_periods() -> None:
    s = series(100, 110, 99, 120, 90, 100)
    assert dd.episodes_from_drawdown(dd.drawdown_series(s), 5) == dd.drawdown_periods(s, 5)
