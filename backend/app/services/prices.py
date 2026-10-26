"""Adjusted-close prices: live yfinance download, on-disk CSV cache, offline snapshot fallback."""

import os
import re
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from app.config import settings

CACHE_TTL_SECONDS = 12 * 3600
RETRIES = 3
BACKOFF_SECONDS = 1.5


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


def get_series(ticker: str, years: int = 2) -> tuple[pd.Series | None, str | None]:
    """Return (series, warning). Order: fresh cache, network, snapshot."""
    cache = settings.cache_dir / filename(ticker)
    if not is_offline():
        if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_SECONDS:
            cached = read_series(cache)
            if cached is not None:
                return _window(cached, years), None
        live = download(ticker, years)
        if live is not None:
            write_series(cache, live)
            return live, None
    snap = read_series(settings.snapshot_dir / filename(ticker))
    if snap is not None:
        return _window(
            snap, years
        ), f"Using bundled price snapshot for {ticker} (live data unavailable)."
    return None, f"No price data available for {ticker}."


def _window(series: pd.Series, years: int) -> pd.Series:
    start = series.index.max() - pd.DateOffset(years=years)
    return series[series.index >= start]


def get_prices(tickers: list[str], years: int = 2) -> tuple[pd.DataFrame, list[str]]:
    """Adjusted closes, one column per ticker that has data, plus warnings."""
    columns: dict[str, pd.Series] = {}
    warnings: list[str] = []
    for ticker in tickers:
        series, warning = get_series(ticker, years)
        if warning:
            warnings.append(warning)
        if series is not None:
            columns[ticker] = series
    return pd.DataFrame(columns).sort_index(), warnings
