"""Request-level orchestration: resolve tickers, fetch data, run the analytics engine."""

from app.analytics import engine
from app.config import settings
from app.schemas import AnalysisResult, AnalyzeRequest, Currency
from app.services import fx, prices, sectors, tickers

INDIA_BENCHMARK = "^NSEI"
US_BENCHMARK = "^GSPC"


class PipelineError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def default_benchmark(holdings: list, base_currency: Currency) -> str:
    """Nifty 50 if most value is Indian, S&P 500 otherwise. Value is in the base currency."""
    india = sum(h.market_value for h in holdings if h.price_currency == "INR")
    total = sum(h.market_value for h in holdings)
    return INDIA_BENCHMARK if total and india / total > 0.5 else US_BENCHMARK


def run_analysis(req: AnalyzeRequest) -> AnalysisResult:
    if len(req.holdings) > settings.max_rows:
        raise PipelineError(f"At most {settings.max_rows} holdings are allowed.", 413)

    warnings: list[str] = []
    symbols = list(dict.fromkeys(h.symbol for h in req.holdings))
    mapping, unresolved = tickers.resolve_symbols(
        symbols, exchanges={h.symbol: h.exchange for h in req.holdings}
    )
    if unresolved:
        warnings.append("Unresolved symbols (excluded): " + ", ".join(unresolved))
    if not mapping:
        raise PipelineError("None of the symbols could be resolved to a Yahoo Finance ticker.")

    needed = sorted(set(mapping.values()))
    px, price_warnings, live_failed = prices.fetch_many(needed, req.lookback_years)
    warnings += price_warnings
    allow_network = not live_failed

    needs_fx = any(engine.ticker_currency(t) != req.base_currency for t in px.columns)
    usdinr = None
    if needs_fx:
        usdinr, fx_warnings = fx.get_usdinr(req.lookback_years, allow_network)
        warnings += fx_warnings
        if usdinr is None:
            raise PipelineError("USD/INR exchange rates are unavailable.", 502)

    sector_map = sectors.get_sectors(needed, allow_network)
    resolved = engine.resolve_holdings(
        req.holdings, mapping, sector_map, px, req.base_currency, usdinr
    )
    if not resolved:
        raise PipelineError("No price data is available for any of the holdings.", 502)
    missing = sorted(
        {h.symbol for h in req.holdings} - {h.symbol for h in resolved} - set(unresolved)
    )
    if missing:
        warnings.append("No price data (excluded): " + ", ".join(missing))

    benchmark = req.benchmark or default_benchmark(resolved, req.base_currency)
    bench_fetch = prices.fetch(benchmark, req.lookback_years, allow_network)
    if bench_fetch.warning:
        warnings.append(bench_fetch.warning)
    if bench_fetch.series is None:
        raise PipelineError(f"No price data for benchmark {benchmark}.", 502)

    try:
        return engine.analyze(
            resolved,
            px,
            bench_fetch.series,
            benchmark,
            req.base_currency,
            usdinr,
            warnings=_dedupe(warnings),
        )
    except ValueError as exc:
        raise PipelineError(str(exc)) from exc


SNAPSHOT_PREFIX = "Using bundled price snapshot for "


def _dedupe(items: list[str]) -> list[str]:
    """Drop repeats and merge the per-ticker snapshot warnings into one."""
    snapshot = [
        w.removeprefix(SNAPSHOT_PREFIX).split(" (")[0]
        for w in items
        if w.startswith(SNAPSHOT_PREFIX)
    ]
    rest = [w for w in dict.fromkeys(items) if not w.startswith(SNAPSHOT_PREFIX)]
    if snapshot:
        rest.insert(
            0,
            "Live prices unavailable; using the bundled price snapshot for: "
            + ", ".join(dict.fromkeys(snapshot)),
        )
    return rest
