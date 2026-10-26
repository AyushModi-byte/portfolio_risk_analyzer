"""Sector lookup: yfinance first, bundled sector_map.csv as fallback."""

from functools import lru_cache

import pandas as pd
import yfinance as yf

from app.config import settings
from app.services.cache import TTLCache
from app.services.prices import is_offline

UNKNOWN = "Unknown"


@lru_cache(maxsize=1)
def _sector_map() -> dict[str, str]:
    path = settings.sector_map_path
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    return {str(t).upper(): str(s) for t, s in zip(df["ticker"], df["sector"], strict=True)}


def _from_yfinance(ticker: str) -> str | None:
    try:
        sector = yf.Ticker(ticker).info.get("sector")
    except Exception:
        return None
    return str(sector) if sector else None


_memory: TTLCache[str] = TTLCache(settings.price_ttl_seconds * 4, maxsize=1024)


def get_sector(ticker: str, allow_network: bool = True) -> str:
    if allow_network and not is_offline():
        cached = _memory.get(ticker)
        if cached is not None:
            return cached
        live = _from_yfinance(ticker)
        if live:
            _memory.set(ticker, live)
            return live
    return _sector_map().get(ticker.upper(), UNKNOWN)


def get_sectors(tickers: list[str], allow_network: bool = True) -> dict[str, str]:
    return {t: get_sector(t, allow_network) for t in tickers}
