"""USD/INR daily series, forward-filled over holidays."""

import pandas as pd

from app.services.prices import get_series

USDINR = "USDINR=X"


def get_usdinr(years: int = 2) -> tuple[pd.Series | None, list[str]]:
    series, warning = get_series(USDINR, years)
    warnings = [warning] if warning else []
    if series is None:
        return None, warnings
    daily = series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="D"))
    return daily.ffill().rename(USDINR), warnings
