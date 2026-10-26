"""Map broker symbols to Yahoo Finance tickers."""

import re
from collections.abc import Callable

import yfinance as yf

from app.config import settings
from app.services.cache import TTLCache
from app.services.prices import filename, is_offline

SUFFIXES = (".NS", ".BO")
US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "NYSEARCA", "US"}
_exists_cache: TTLCache[bool] = TTLCache(settings.price_ttl_seconds, maxsize=2048)
_SAFE = re.compile(r"[^A-Z0-9.&^=-]")


def _has_data(ticker: str) -> bool:
    try:
        hist = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
    except Exception:
        return False
    return not hist.empty


def default_exists(ticker: str) -> bool:
    """True if the bundled snapshot has the ticker or (when online) Yahoo returns prices for it."""
    if (settings.snapshot_dir / filename(ticker)).exists():
        return True
    if is_offline():
        return False
    cached = _exists_cache.get(ticker)
    if cached is None:
        cached = _has_data(ticker)
        _exists_cache.set(ticker, cached)
    return cached


def candidates(symbol: str, exchange: str | None = None) -> list[str]:
    """Ordered Yahoo tickers to try: keep an existing .NS/.BO suffix, else .NS, .BO, plain.

    An explicit exchange column narrows the order: US exchanges try the plain symbol only and
    BSE tries .BO first.
    """
    sym = _SAFE.sub("", symbol.strip().upper())
    if not sym:
        return []
    if sym.endswith(SUFFIXES):
        return [sym]
    ex = (exchange or "").strip().upper()
    if ex in US_EXCHANGES:
        return [sym]
    if ex == "BSE":
        return [sym + ".BO", sym + ".NS", sym]
    return [sym + ".NS", sym + ".BO", sym]


def resolve_symbols(
    symbols: list[str],
    exists: Callable[[str], bool] = default_exists,
    exchanges: dict[str, str | None] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Return ({symbol: yahoo_ticker}, unresolved symbols). `exists` is injectable for tests."""
    exchanges = exchanges or {}
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for symbol in symbols:
        match = next((t for t in candidates(symbol, exchanges.get(symbol)) if exists(t)), None)
        if match is None:
            unresolved.append(symbol)
        else:
            resolved[symbol] = match
    return resolved, unresolved
