"""Compare engine metrics with quantstats and numpy on the sample portfolios (offline snapshot).

Prints a results table and writes it to docs/VALIDATION.md.
"""

import sys
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import quantstats as qs  # noqa: E402

from app.analytics import engine  # noqa: E402
from app.analytics import returns as ret  # noqa: E402
from app.config import settings  # noqa: E402

settings.offline = True  # never touch the network; use the bundled snapshot
from app.services import samples  # noqa: E402

TOLERANCE = 0.005  # relative, for volatility, Sharpe, max drawdown and beta
VAR_TOLERANCE = 1e-6
SAMPLE_NAMES = ["india", "us", "mixed"]


@dataclass
class Row:
    portfolio: str
    metric: str
    engine: float
    reference: float
    reference_name: str
    tolerance: float
    relative: bool = True

    @property
    def error(self) -> float:
        diff = abs(self.engine - self.reference)
        if not self.relative:
            return diff
        return diff / abs(self.reference) if self.reference else diff

    @property
    def ok(self) -> bool:
        return self.error <= self.tolerance


def reference_returns(inputs: samples.EngineInputs) -> tuple[pd.Series, pd.Series]:
    """Rebuild portfolio and benchmark returns with plain numpy, independent of engine.analyze."""
    cols = [h.yahoo_ticker for h in inputs.holdings]
    cleaned, dropped = ret.clean_prices(
        inputs.prices[cols], settings.min_history_days, settings.max_ffill_days
    )
    kept = [h for h in inputs.holdings if h.yahoo_ticker not in dropped]
    value = np.zeros(len(cleaned))
    for h in kept:
        px = ret.to_base_currency(
            cleaned[h.yahoo_ticker], h.price_currency, inputs.base_currency, inputs.usdinr
        )
        value += h.quantity * px.to_numpy()
    port = pd.Series(value[1:] / value[:-1] - 1, index=cleaned.index[1:])
    bench = inputs.benchmark_prices.sort_index()
    bench = bench.reindex(bench.index.union(cleaned.index)).ffill().reindex(cleaned.index)
    bench_ret = pd.Series(bench.to_numpy()[1:] / bench.to_numpy()[:-1] - 1, index=cleaned.index[1:])
    return port, bench_ret


def compute_rows(names: list[str] | None = None) -> list[Row]:
    rows: list[Row] = []
    for name in names or SAMPLE_NAMES:
        inputs = samples.load_sample(name)
        result = engine.analyze(
            inputs.holdings,
            inputs.prices,
            inputs.benchmark_prices,
            inputs.benchmark_name,
            inputs.base_currency,
            inputs.usdinr,
        )
        risk = result.risk
        port, bench = reference_returns(inputs)
        covariance = np.cov(port.to_numpy(), bench.to_numpy(), ddof=1)
        rf = risk.risk_free_rate
        assert risk.beta is not None and risk.sharpe is not None
        rows += [
            Row(
                name,
                "Volatility",
                risk.volatility,
                float(qs.stats.volatility(port, periods=252, annualize=True)),
                "quantstats volatility",
                TOLERANCE,
            ),
            Row(
                name,
                "Sharpe",
                risk.sharpe,
                float(qs.stats.sharpe(port, rf=rf, periods=252, annualize=True)),
                "quantstats sharpe",
                TOLERANCE,
            ),
            Row(
                name,
                "Max drawdown",
                risk.max_drawdown,
                float(qs.stats.max_drawdown(port)),
                "quantstats max_drawdown",
                TOLERANCE,
            ),
            Row(
                name,
                "Beta",
                risk.beta,
                float(covariance[0, 1] / covariance[1, 1]),
                "numpy covariance",
                TOLERANCE,
            ),
            Row(
                name,
                "VaR 95",
                risk.var_95,
                float(-np.percentile(port.to_numpy(), 5)),
                "numpy percentile",
                VAR_TOLERANCE,
                relative=False,
            ),
        ]
    return rows


def render(rows: list[Row]) -> str:
    lines = [
        "| Portfolio | Metric | Engine | Reference | Reference source | Error | Tolerance | Pass |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | :---: |",
    ]
    for r in rows:
        kind = "rel" if r.relative else "abs"
        lines.append(
            f"| {r.portfolio} | {r.metric} | {r.engine:.6f} | {r.reference:.6f} | "
            f"{r.reference_name} | {r.error:.2e} ({kind}) | {r.tolerance:.0e} | "
            f"{'yes' if r.ok else 'NO'} |"
        )
    return "\n".join(lines)


def write_report(rows: list[Row]) -> Path:
    path = ROOT / "docs" / "VALIDATION.md"
    verdict = (
        "All metrics are within tolerance."
        if all(r.ok for r in rows)
        else ("Some metrics are outside tolerance; see the rows marked NO.")
    )
    text = f"""# Metric Validation

Generated by `python scripts/validate_metrics.py` on {date.today().isoformat()}.
Prices come from the offline snapshot in `backend/data/price_snapshot`, 2-year lookback ending
at the last snapshot date. {verdict}

Setup: the reference portfolio returns are rebuilt with plain numpy from the same cleaned,
base-currency prices, then passed to quantstats (252 periods, same risk-free rate as the engine:
{settings.risk_free_inr:.2f} for INR, {settings.risk_free_usd:.2f} for USD). Beta uses `np.cov`
on the same portfolio and benchmark returns. VaR uses `np.percentile` (linear interpolation).

Tolerances: 0.5% relative error for volatility, Sharpe, max drawdown and beta; 1e-6 absolute
for VaR.

{render(rows)}

Notes:

- Sharpe: both use the same convention, de-annualizing the risk-free rate by compounding,
  `(1 + rf) ** (1 / 252) - 1` (see METRICS.md). Earlier the engine used the arithmetic `rf / 252`,
  which differed from quantstats by about 2% on india (-1.0039 vs -0.9851); the engine and
  METRICS.md were changed to the compounded convention.
- The mixed portfolio is valued in INR (USD holdings converted with USDINR=X), benchmark ^NSEI.
  The US portfolio is valued in USD with benchmark ^GSPC.
- The benchmark is forward-filled onto the portfolio calendar so holidays in one market do not drop
  days of the other.
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    rows = compute_rows()
    print(render(rows))
    print(f"\nWrote {write_report(rows)}")
    failed = [r for r in rows if not r.ok]
    if failed:
        print(f"\n{len(failed)} metric(s) outside tolerance")
        return 1
    print("\nAll metrics within tolerance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
