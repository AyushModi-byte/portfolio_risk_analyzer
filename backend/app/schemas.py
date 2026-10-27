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
    volatility: float | None = None  # annualized, base currency; used for risk contribution


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
    weights: list[WeightItem] = Field(max_length=500)
    sector_exposure: list[SectorExposure] = Field(max_length=50)
    risk: RiskMetrics
    drawdown_series: list[DrawdownPoint] = Field(max_length=3000)
    correlation: CorrelationMatrix
    warnings: list[str] = Field(default_factory=list, max_length=50)
    disclaimer: str = DISCLAIMER


class AnalyzeRequest(BaseModel):
    holdings: list[Holding] = Field(min_length=1)
    base_currency: Currency = "INR"
    benchmark: str | None = Field(default=None, pattern=r"^[A-Za-z0-9^.=\-]{1,20}$")
    lookback_years: int = Field(default=2, ge=1, le=5)


class SampleInfo(BaseModel):
    name: str
    base_currency: Currency
    benchmark: str
    holdings: list[Holding]
