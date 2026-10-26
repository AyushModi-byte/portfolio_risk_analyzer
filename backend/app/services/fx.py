"""USD/INR daily series, forward-filled over holidays."""

import pandas as pd

from app.services.prices import fetch

USDINR = "USDINR=X"


def get_usdinr(years: int = 2, allow_network: bool = True) -> tuple[pd.Series | None, list[str]]:
    series, warning, _ = fetch(USDINR, years, allow_network)
    warnings = [warning] if warning else []
    if series is None:
        return None, warnings
    daily = series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="D"))
    return daily.ffill().rename(USDINR), warnings
