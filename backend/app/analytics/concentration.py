import pandas as pd


def weights(market_values: pd.Series) -> pd.Series:
    return market_values / market_values.sum()


def hhi(w: pd.Series) -> float:
    return float((w**2).sum())


def effective_n(w: pd.Series) -> float:
    return 1.0 / hhi(w)


def top_n_concentration(w: pd.Series, n: int = 5) -> float:
    return float(w.nlargest(n).sum())


def sector_exposure(w: pd.Series, sectors: pd.Series) -> pd.Series:
    """Sum of weights per sector, largest first. Both series are indexed by holding."""
    return w.groupby(sectors.reindex(w.index).fillna("Unknown")).sum().sort_values(ascending=False)
