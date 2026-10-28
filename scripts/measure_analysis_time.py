"""Measure how long POST /api/analyze takes for the sample portfolios and a 20-stock portfolio.

    python scripts/measure_analysis_time.py            # live yfinance, writes docs/PERFORMANCE.md
    python scripts/measure_analysis_time.py --offline  # bundled snapshot only (no network)

Timings are wall-clock seconds around the in-process request (routing, validation, price lookup,
analytics, serialization), measured with FastAPI's TestClient, so they exclude network latency
between a browser and the server.

Cold = empty in-memory and disk caches (every price is downloaded). Warm = same request again
with the caches filled. Live runs that fell back to the snapshot are reported separately and
never counted as live.
"""

import argparse
import platform
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import prices, samples, sectors, tickers  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

COLD_RUNS = 3
WARM_RUNS = 5
SNAPSHOT_WARNING = "Live prices unavailable"

# 10 NSE and 10 US stocks that all exist in the bundled snapshot.
TWENTY_STOCKS = [
    ("RELIANCE", "NSE"),
    ("TCS", "NSE"),
    ("HDFCBANK", "NSE"),
    ("INFY", "NSE"),
    ("ICICIBANK", "NSE"),
    ("ITC", "NSE"),
    ("LT", "NSE"),
    ("MARUTI", "NSE"),
    ("SUNPHARMA", "NSE"),
    ("NTPC", "NSE"),
    ("AAPL", None),
    ("MSFT", None),
    ("GOOGL", None),
    ("AMZN", None),
    ("JPM", None),
    ("V", None),
    ("JNJ", None),
    ("PG", None),
    ("XOM", None),
    ("CAT", None),
]


def clear_caches() -> None:
    prices._memory.clear()
    sectors._memory.clear()
    tickers._exists_cache.clear()
    settings.cache_dir = Path(tempfile.mkdtemp(prefix="price_cache_"))


def portfolios() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in samples.list_samples():
        file = samples.SAMPLES_DIR / f"{name}.csv"
        holdings = samples.parsers.parse_holdings(file.name, file.read_bytes()).holdings
        currency, benchmark = samples.SAMPLE_SETUP[name]
        out[name] = {
            "holdings": [h.model_dump(mode="json") for h in holdings],
            "base_currency": currency,
            "benchmark": benchmark,
        }
    twenty = [
        {"symbol": s, "quantity": 10, "exchange": e, "currency": "INR" if e else "USD"}
        for s, e in TWENTY_STOCKS
    ]
    out["20-stock mixed"] = {"holdings": twenty, "base_currency": "INR", "benchmark": "^NSEI"}
    return out


def timed(client: TestClient, body: dict[str, Any]) -> tuple[float, bool, int]:
    start = time.perf_counter()
    resp = client.post("/api/analyze", json=body)
    seconds = time.perf_counter() - start
    data = resp.json() if resp.status_code == 200 else {}
    fell_back = any(SNAPSHOT_WARNING in w for w in data.get("warnings", []))
    return seconds, fell_back, resp.status_code


def span(values: list[float]) -> str:
    return f"{statistics.median(values):.2f} ({min(values):.2f} to {max(values):.2f})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="use only the bundled snapshot")
    parser.add_argument("--no-write", action="store_true", help="print only")
    args = parser.parse_args()
    settings.offline = args.offline
    client = TestClient(app)

    # Import-time work (first request loads the sector map, pandas internals) is not what we
    # measure, so run one throwaway request first.
    clear_caches()
    first = portfolios()["us"]
    timed(client, first)

    rows: list[str] = []
    for name, body in portfolios().items():
        n = len(body["holdings"])
        cold: list[float] = []
        warm: list[float] = []
        fallbacks = 0
        for _ in range(COLD_RUNS):
            clear_caches()
            seconds, fell_back, status = timed(client, body)
            assert status == 200, (name, status)
            fallbacks += fell_back
            cold.append(seconds)
            for _ in range(WARM_RUNS if len(cold) == 1 else 0):
                w, w_fell_back, w_status = timed(client, body)
                assert w_status == 200, (name, w_status)
                fallbacks += w_fell_back
                warm.append(w)
        note = f"{fallbacks} runs used the snapshot" if fallbacks and not args.offline else ""
        warm_cell = span(warm) if not args.offline else "same as cold"
        cold_cell = span(cold)
        rows.append(f"| {name} | {n} | {cold_cell} | {warm_cell} | {note} |")
        print(rows[-1])

    mode = "offline snapshot (no network)" if args.offline else "live yfinance"
    header = (
        "| Portfolio | Holdings | Cold, seconds: median (range of "
        f"{COLD_RUNS}) | Warm, seconds: median (range of {WARM_RUNS}) | Notes |\n"
        "| --- | ---: | ---: | ---: | --- |"
    )
    table = header + "\n" + "\n".join(rows)
    report = (
        f"# Analysis time\n\nGenerated by `python scripts/measure_analysis_time.py"
        f"{' --offline' if args.offline else ''}` on {date.today().isoformat()}.\n\n"
        f"- Mode: {mode}, 2-year lookback.\n"
        f"- Machine: {platform.system()} {platform.release()}, Python {platform.python_version()}, "
        "a laptop, not the deployed server.\n"
        "- Measured around `POST /api/analyze` in-process (no browser-to-server network).\n"
        "- Cold = empty memory and disk caches; warm = the same request with caches filled.\n"
        + (
            "- Offline mode reads the snapshot every time, so cold and warm are the same.\n"
            if args.offline
            else "- Live timings depend on Yahoo Finance response times and vary run to run.\n"
        )
        + f"\n{table}\n"
    )
    print("\n" + report)
    if not args.no_write:
        name = "PERFORMANCE_OFFLINE.md" if args.offline else "PERFORMANCE.md"
        (ROOT / "docs" / name).write_text(report, encoding="utf-8")
        print(f"wrote docs/{name}")


if __name__ == "__main__":
    main()
