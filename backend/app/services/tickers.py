"""Map broker symbols to Yahoo Finance tickers."""

import re
from collections.abc import Callable

import yfinance as yf

SUFFIXES = (".NS", ".BO")
_SAFE = re.compile(r"[^A-Z0-9.&^=-]")


def _has_data(ticker: str) -> bool:
    try:
        hist = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
    except Exception:
        return False
    return not hist.empty


def candidates(symbol: str) -> list[str]:
    """Ordered Yahoo tickers to try: keep an existing .NS/.BO suffix, else .NS, .BO, plain."""
    sym = _SAFE.sub("", symbol.strip().upper())
    if not sym:
        return []
    if sym.endswith(SUFFIXES):
        return [sym]
    return [sym + ".NS", sym + ".BO", sym]


def resolve_symbols(
    symbols: list[str], exists: Callable[[str], bool] = _has_data
) -> tuple[dict[str, str], list[str]]:
    """Return ({symbol: yahoo_ticker}, unresolved symbols). `exists` is injectable for tests."""
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for symbol in symbols:
        match = next((t for t in candidates(symbol) if exists(t)), None)
        if match is None:
            unresolved.append(symbol)
        else:
            resolved[symbol] = match
    return resolved, unresolved
