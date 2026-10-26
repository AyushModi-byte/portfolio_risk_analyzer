"""Load the bundled sample portfolios into engine inputs using prices from the local snapshot."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.analytics.engine import resolve_holdings
from app.config import BACKEND_DIR, settings
from app.schemas import Currency, ResolvedHolding
from app.services import fx, parsers, prices, sectors, tickers

SAMPLES_DIR = BACKEND_DIR / "data" / "sample_portfolios"
SAMPLE_SETUP: dict[str, tuple[Currency, str]] = {
    "india": ("INR", "^NSEI"),
    "us": ("USD", "^GSPC"),
    "mixed": ("INR", "^NSEI"),
}


@dataclass
class EngineInputs:
    holdings: list[ResolvedHolding]
    prices: pd.DataFrame
    benchmark_prices: pd.Series
    benchmark_name: str
    base_currency: Currency
    usdinr: pd.Series | None
    warnings: list[str]


def list_samples() -> list[str]:
    return sorted(p.stem for p in SAMPLES_DIR.glob("*.csv"))


def _snapshot_has(ticker: str) -> bool:
    return (settings.snapshot_dir / prices.filename(ticker)).exists()


def load_sample(name: str, years: int = 2, path: Path | None = None) -> EngineInputs:
    base, bench_name = SAMPLE_SETUP[name]
    file = path or SAMPLES_DIR / f"{name}.csv"
    parsed = parsers.parse_holdings(file.name, file.read_bytes())
    mapping, unresolved = tickers.resolve_symbols(
        [h.symbol for h in parsed.holdings], exists=_snapshot_has
    )
    warnings = list(parsed.warnings)
    if unresolved:
        warnings.append("Unresolved symbols: " + ", ".join(unresolved))
    px, price_warnings = prices.get_prices(sorted(set(mapping.values())), years)
    usdinr, fx_warnings = fx.get_usdinr(years)
    bench, bench_warning = prices.get_series(bench_name, years)
    if bench is None:
        raise ValueError(f"No benchmark data for {bench_name}")
    resolved = resolve_holdings(
        parsed.holdings,
        mapping,
        sectors.get_sectors(sorted(set(mapping.values()))),
        px,
        base,
        usdinr,
    )
    return EngineInputs(
        holdings=resolved,
        prices=px,
        benchmark_prices=bench,
        benchmark_name=bench_name,
        base_currency=base,
        usdinr=usdinr,
        warnings=warnings
        + price_warnings
        + fx_warnings
        + ([bench_warning] if bench_warning else []),
    )
