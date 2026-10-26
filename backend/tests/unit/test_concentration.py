import pandas as pd
import pytest

from app.analytics import concentration as conc


def test_two_equal_stocks() -> None:
    w = conc.weights(pd.Series({"A": 500.0, "B": 500.0}))
    assert w.tolist() == [0.5, 0.5]
    assert conc.hhi(w) == pytest.approx(0.5, abs=1e-6)
    assert conc.effective_n(w) == pytest.approx(2.0, abs=1e-6)


def test_weights_sum_to_one_and_scale() -> None:
    w = conc.weights(pd.Series({"A": 1.0, "B": 3.0}))
    assert w["A"] == pytest.approx(0.25, abs=1e-6)
    assert w.sum() == pytest.approx(1.0, abs=1e-12)


def test_single_stock_is_fully_concentrated() -> None:
    w = conc.weights(pd.Series({"A": 42.0}))
    assert conc.hhi(w) == 1.0
    assert conc.effective_n(w) == 1.0


def test_top5_concentration() -> None:
    w = pd.Series([0.3, 0.2, 0.15, 0.1, 0.1, 0.1, 0.05], index=list("ABCDEFG"))
    assert conc.top_n_concentration(w, 5) == pytest.approx(0.85, abs=1e-6)


def test_top5_with_fewer_holdings_is_one() -> None:
    w = pd.Series([0.5, 0.5], index=["A", "B"])
    assert conc.top_n_concentration(w) == pytest.approx(1.0, abs=1e-6)


def test_sector_exposure_sums_and_sorts() -> None:
    w = pd.Series({"A": 0.4, "B": 0.1, "C": 0.5})
    sectors = pd.Series({"A": "Tech", "B": "Tech", "C": "Energy"})
    out = conc.sector_exposure(w, sectors)
    assert out.to_dict() == pytest.approx({"Energy": 0.5, "Tech": 0.5}, abs=1e-6)


def test_sector_exposure_missing_sector_is_unknown() -> None:
    w = pd.Series({"A": 0.6, "B": 0.4})
    out = conc.sector_exposure(w, pd.Series({"A": "Tech"}))
    assert out["Unknown"] == pytest.approx(0.4, abs=1e-6)
