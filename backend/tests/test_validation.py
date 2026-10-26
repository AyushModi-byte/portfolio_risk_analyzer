"""Engine metrics vs quantstats and numpy on the sample portfolios, using the offline snapshot."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import validate_metrics as vm  # noqa: E402


@pytest.fixture(scope="module")
def rows() -> list[vm.Row]:
    return vm.compute_rows()


@pytest.mark.parametrize("portfolio", vm.SAMPLE_NAMES)
@pytest.mark.parametrize("metric", ["Volatility", "Sharpe", "Max drawdown", "Beta", "VaR 95"])
def test_metric_matches_reference(rows: list[vm.Row], portfolio: str, metric: str) -> None:
    row = next(r for r in rows if r.portfolio == portfolio and r.metric == metric)
    assert row.ok, f"{portfolio} {metric}: engine {row.engine} vs {row.reference} ({row.error:.2e})"
