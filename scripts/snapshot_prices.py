"""Download prices for the sample portfolios and benchmarks into backend/data/price_snapshot."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import settings  # noqa: E402
from app.services import parsers, prices, tickers  # noqa: E402

YEARS = 5
BENCHMARKS = ["^NSEI", "^GSPC", "USDINR=X"]
SAMPLES = BACKEND / "data" / "sample_portfolios"


def sample_tickers() -> list[str]:
    found: list[str] = []
    for path in sorted(SAMPLES.glob("*.csv")):
        result = parsers.parse_holdings(path.name, path.read_bytes())
        for holding in result.holdings:
            ticker = tickers.candidates(holding.symbol)[0]
            exchange = (holding.exchange or "").upper()
            if exchange in {"NASDAQ", "NYSE"} or holding.currency == "USD" or path.stem == "us":
                ticker = holding.symbol
            if ticker not in found:
                found.append(ticker)
    return found


def main() -> int:
    failed: list[str] = []
    for ticker in sample_tickers() + BENCHMARKS:
        series = prices.download(ticker, YEARS)
        if series is None:
            failed.append(ticker)
            print(f"FAILED  {ticker}")
            continue
        prices.write_series(settings.snapshot_dir / prices.filename(ticker), series)
        span = f"{series.index.min().date()} -> {series.index.max().date()}"
        print(f"ok      {ticker:<14} {len(series)} rows  {span}")
    if failed:
        print("Failed tickers:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
