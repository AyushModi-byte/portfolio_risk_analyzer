import pandas as pd
import pytest

from app.analytics import correlation as cor


def matrix() -> pd.DataFrame:
    names = ["A", "B", "C"]
    values = [[1.0, 0.9, 0.1], [0.9, 1.0, -0.3], [0.1, -0.3, 1.0]]
    return pd.DataFrame(values, index=names, columns=names)


def test_summary_average_and_extremes() -> None:
    out = cor.correlation_summary(matrix(), n=1)
    assert out["pair_count"] == 3
    assert out["average"] == pytest.approx((0.9 + 0.1 - 0.3) / 3, abs=1e-12)
    assert out["most_correlated"] == [{"a": "A", "b": "B", "correlation": 0.9}]
    assert out["least_correlated"] == [{"a": "B", "b": "C", "correlation": -0.3}]


def test_summary_single_holding() -> None:
    out = cor.correlation_summary(pd.DataFrame([[1.0]], index=["A"], columns=["A"]))
    assert out["pair_count"] == 0 and out["average"] is None


def test_correlations_with_symbol() -> None:
    out = cor.correlations_with(matrix(), "A", n=1)
    assert out["highest"] == [{"symbol": "B", "correlation": 0.9}]
    assert out["lowest"] == [{"symbol": "C", "correlation": 0.1}]
    assert out["average"] == pytest.approx(0.5, abs=1e-12)
