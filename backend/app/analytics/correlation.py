import numpy as np
import pandas as pd


def correlation_summary(corr: pd.DataFrame, n: int = 3) -> dict[str, object]:
    """Average pairwise correlation and the n most / least correlated pairs."""
    names = list(corr.index)
    pairs = [
        (names[i], names[j], float(corr.iloc[i, j]))
        for i in range(len(names))
        for j in range(i + 1, len(names))
    ]
    if not pairs:
        return {"pair_count": 0, "average": None, "most_correlated": [], "least_correlated": []}
    ordered = sorted(pairs, key=lambda p: p[2], reverse=True)

    def row(p: tuple[str, str, float]) -> dict[str, object]:
        return {"a": p[0], "b": p[1], "correlation": p[2]}

    return {
        "pair_count": len(pairs),
        "average": float(np.mean([p[2] for p in pairs])),
        "most_correlated": [row(p) for p in ordered[:n]],
        "least_correlated": [row(p) for p in ordered[::-1][:n]],
    }


def correlations_with(corr: pd.DataFrame, symbol: str, n: int = 3) -> dict[str, object]:
    """Correlations of one holding with the others, highest first."""
    others = corr[symbol].drop(symbol).sort_values(ascending=False)
    rows = [{"symbol": s, "correlation": float(v)} for s, v in others.items()]
    return {
        "symbol": symbol,
        "average": float(others.mean()) if len(others) else None,
        "highest": rows[:n],
        "lowest": rows[::-1][:n],
    }
