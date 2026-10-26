import pandas as pd


def drawdown_series(values: pd.Series) -> pd.Series:
    """DD_t = V_t / max_{s<=t} V_s - 1."""
    return values / values.cummax() - 1


def max_drawdown(values: pd.Series) -> float:
    return float(drawdown_series(values).min())


def drawdown_periods(values: pd.Series, n: int = 3) -> list[dict[str, object]]:
    """The n deepest drawdown episodes, deepest first.

    An episode runs from the last all-time high to the next one. `recovery_date` is None while
    the episode is still open. Day counts are calendar days.
    """
    return episodes_from_drawdown(drawdown_series(values), n)


def episodes_from_drawdown(dd: pd.Series, n: int = 3) -> list[dict[str, object]]:
    """Same as drawdown_periods, starting from an existing drawdown series."""
    episodes: list[dict[str, object]] = []
    start: int | None = None
    for i in range(len(dd)):
        if dd.iloc[i] < 0 and start is None:
            start = i
        elif dd.iloc[i] >= 0 and start is not None:
            episodes.append(_episode(dd, start, i))
            start = None
    if start is not None:
        episodes.append(_episode(dd, start, None))
    episodes.sort(key=lambda e: float(e["depth"]))  # type: ignore[arg-type]
    return episodes[:n]


def _episode(dd: pd.Series, start: int, end: int | None) -> dict[str, object]:
    stop = len(dd) if end is None else end
    window = dd.iloc[start:stop]
    peak = dd.index[max(start - 1, 0)]
    trough = window.idxmin()
    recovery = None if end is None else dd.index[end]
    return {
        "peak_date": peak.strftime("%Y-%m-%d"),
        "trough_date": trough.strftime("%Y-%m-%d"),
        "recovery_date": None if recovery is None else recovery.strftime("%Y-%m-%d"),
        "depth": float(window.min()),
        "days_peak_to_trough": int((trough - peak).days),
        "days_to_recover": None if recovery is None else int((recovery - trough).days),
    }
