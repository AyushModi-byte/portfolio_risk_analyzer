"""Adjusted-close prices: live yfinance download, on-disk CSV cache, offline snapshot fallback."""

import os
import re
import time
from pathlib import Path
from typing import NamedTuple

import pandas as pd
import yfinance as yf

from app.config import settings
from app.services.cache import TTLCache

CACHE_TTL_SECONDS = 12 * 3600
RETRIES = 3
BACKOFF_SECONDS = 1.5

_memory: TTLCache[pd.Series] = TTLCache(settings.price_ttl_seconds, maxsize=512)


def filename(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9.=_-]", "_", ticker) + ".csv"


def read_series(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if df.empty:
        return None
    series = df.iloc[:, 0].astype(float).dropna()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None)
    return series.sort_index()


def write_series(path: Path, series: pd.Series) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    series.rename("Close").rename_axis("Date").to_csv(path)


def download(ticker: str, years: int) -> pd.Series | None:
    """Download adjusted closes with retries; None if nothing came back."""
    for attempt in range(RETRIES):
        try:
            hist = yf.Ticker(ticker).history(period=f"{years}y", auto_adjust=True)
            if not hist.empty:
                series = hist["Close"].astype(float).dropna()
                series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
                return series[~series.index.duplicated(keep="last")]
        except Exception:
            pass
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF_SECONDS * (attempt + 1))
    return None


def is_offline() -> bool:
    return settings.offline or os.environ.get("OFFLINE") == "1"


class Fetched(NamedTuple):
    series: pd.Series | None
    warning: str | None
    live_failed: bool  # a live download was allowed and failed


def fetch(ticker: str, years: int = 2, allow_network: bool = True) -> Fetched:
    """Order: memory TTL cache, fresh disk cache, network, bundled snapshot."""
    network = allow_network and not is_offline()
    key = (ticker, years)
    cache = settings.cache_dir / filename(ticker)
    if network:
        hit = _memory.get(key)
        if hit is not None:
            return Fetched(hit.copy(), None, False)
        if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_SECONDS:
            cached = read_series(cache)
            if cached is not None:
                series = _window(cached, years)
                _memory.set(key, series)
                return Fetched(series.copy(), None, False)
        live = download(ticker, years)
        if live is not None:
            write_series(cache, live)
            _memory.set(key, live)
            return Fetched(live.copy(), None, False)
    snap = read_series(settings.snapshot_dir / filename(ticker))
    if snap is not None:
        warning = f"Using bundled price snapshot for {ticker} (live data unavailable)."
        return Fetched(_window(snap, years), warning, network)
    return Fetched(None, f"No price data available for {ticker}.", network)


def get_series(ticker: str, years: int = 2) -> tuple[pd.Series | None, str | None]:
    """Return (series, warning)."""
    f = fetch(ticker, years)
    return f.series, f.warning


def _window(series: pd.Series, years: int) -> pd.Series:
    start = series.index.max() - pd.DateOffset(years=years)
    return series[series.index >= start]


def fetch_many(tickers: list[str], years: int = 2) -> tuple[pd.DataFrame, list[str], bool]:
    """Adjusted closes, one column per ticker with data, warnings, and whether live data failed.

    After the first failed live download the rest are served from the snapshot without retrying,
    so a yfinance outage costs one retry cycle, not one per ticker.
    """
    columns: dict[str, pd.Series] = {}
    warnings: list[str] = []
    allow_network = True
    live_failed = False
    for ticker in tickers:
        f = fetch(ticker, years, allow_network)
        if f.live_failed:
            allow_network = False
            live_failed = True
        if f.warning:
            warnings.append(f.warning)
        if f.series is not None:
            columns[ticker] = f.series
    return pd.DataFrame(columns).sort_index(), warnings, live_failed


def get_prices(tickers: list[str], years: int = 2) -> tuple[pd.DataFrame, list[str]]:
    """Adjusted closes, one column per ticker that has data, plus warnings."""
    df, warnings, _ = fetch_many(tickers, years)
    return df, warnings
