import pandas as pd


def drawdown_series(values: pd.Series) -> pd.Series:
    """DD_t = V_t / max_{s<=t} V_s - 1."""
    return values / values.cummax() - 1


def max_drawdown(values: pd.Series) -> float:
    return float(drawdown_series(values).min())
