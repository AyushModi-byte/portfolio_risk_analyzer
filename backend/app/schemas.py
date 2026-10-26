from typing import Literal

from pydantic import BaseModel, Field

DISCLAIMER = "Analytics only, not financial advice."

Currency = Literal["INR", "USD"]


class Holding(BaseModel):
    symbol: str
    name: str | None = None
    quantity: float = Field(gt=0)
    avg_buy_price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    exchange: str | None = None


class ResolvedHolding(Holding):
    yahoo_ticker: str
    sector: str = "Unknown"
    latest_price: float
    price_currency: Currency
    market_value: float  # base currency
    invested: float | None = None  # base currency, None if no buy price


class Summary(BaseModel):
    value: float
    invested: float
    pnl: float
    pnl_pct: float | None
    base_currency: Currency


class WeightItem(BaseModel):
    symbol: str
    weight: float
    market_value: float


class SectorExposure(BaseModel):
    sector: str
    weight: float


class RiskMetrics(BaseModel):
    volatility: float
    beta: float | None
    sharpe: float | None
    var_95: float
    max_drawdown: float
    risk_free_rate: float
    benchmark: str
    trading_days: int
    observations: int
    hhi: float
    effective_n: float
    top5_concentration: float


class DrawdownPoint(BaseModel):
    date: str
    drawdown: float


class CorrelationMatrix(BaseModel):
    symbols: list[str]
    values: list[list[float]]


class AnalysisResult(BaseModel):
    summary: Summary
    weights: list[WeightItem]
    sector_exposure: list[SectorExposure]
    risk: RiskMetrics
    drawdown_series: list[DrawdownPoint]
    correlation: CorrelationMatrix
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
