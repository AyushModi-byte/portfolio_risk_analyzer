import numpy as np
import pandas as pd


def annualized_volatility(returns: pd.Series, trading_days: int = 252) -> float:
    return float(returns.std(ddof=1) * np.sqrt(trading_days))


def beta(portfolio: pd.Series, benchmark: pd.Series) -> float | None:
    """Cov(rp, rb) / Var(rb) on the common dates; None if the benchmark has no variance."""
    joined = pd.concat([portfolio, benchmark], axis=1, join="inner").dropna()
    if len(joined) < 2:
        return None
    cov = np.cov(joined.iloc[:, 0], joined.iloc[:, 1], ddof=1)
    return None if cov[1, 1] == 0 else float(cov[0, 1] / cov[1, 1])


def sharpe_ratio(returns: pd.Series, risk_free: float, trading_days: int = 252) -> float | None:
    """Annualized Sharpe on excess returns; None if volatility is zero.

    The annual risk-free rate is de-annualized by compounding, (1 + rf) ** (1 / n) - 1,
    the same convention as quantstats.
    """
    std = returns.std(ddof=1)
    if std == 0:
        return None
    daily_rf = (1 + risk_free) ** (1 / trading_days) - 1
    return float((returns.mean() - daily_rf) / std * np.sqrt(trading_days))


def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """1-day historical VaR as a positive loss fraction."""
    return float(-np.percentile(returns, (1 - confidence) * 100))
