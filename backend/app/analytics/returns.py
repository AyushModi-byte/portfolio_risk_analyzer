import pandas as pd


def clean_prices(
    prices: pd.DataFrame, min_days: int = 60, max_ffill_days: int = 5
) -> tuple[pd.DataFrame, list[str]]:
    """Forward-fill gaps up to max_ffill_days and drop stocks with too little history.

    Returns the cleaned frame (rows where every kept stock has a price) and the dropped columns.
    """
    filled = prices.sort_index().ffill(limit=max_ffill_days)
    dropped = [c for c in filled.columns if filled[c].count() < min_days]
    kept = filled.drop(columns=dropped)
    return kept.dropna(how="any"), dropped


def to_base_currency(
    prices: pd.Series, price_currency: str, base_currency: str, usdinr: pd.Series | None
) -> pd.Series:
    """Convert a price series into the base currency using a USDINR series."""
    if price_currency == base_currency:
        return prices
    if usdinr is None:
        raise ValueError("USDINR series required for cross-currency conversion")
    fx = usdinr.reindex(prices.index.union(usdinr.index)).ffill().reindex(prices.index)
    return prices * fx if base_currency == "INR" else prices / fx


def portfolio_value(prices: pd.DataFrame, quantities: pd.Series) -> pd.Series:
    """V_t = sum_i q_i * P_i,t with prices already in the base currency."""
    return prices.mul(quantities.reindex(prices.columns), axis=1).sum(axis=1)


def daily_returns(values: pd.Series) -> pd.Series:
    """Simple daily returns r_t = V_t / V_{t-1} - 1."""
    return values.pct_change().dropna()
