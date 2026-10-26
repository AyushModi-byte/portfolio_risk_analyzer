import pandas as pd

from app.analytics import concentration as conc
from app.analytics import drawdown as dd
from app.analytics import returns as ret
from app.analytics import risk
from app.config import settings
from app.schemas import (
    DISCLAIMER,
    AnalysisResult,
    CorrelationMatrix,
    Currency,
    DrawdownPoint,
    Holding,
    ResolvedHolding,
    RiskMetrics,
    SectorExposure,
    Summary,
    WeightItem,
)


def ticker_currency(ticker: str) -> Currency:
    return "INR" if ticker.upper().endswith((".NS", ".BO")) else "USD"


def default_risk_free(base_currency: Currency) -> float:
    return settings.risk_free_inr if base_currency == "INR" else settings.risk_free_usd


def resolve_holdings(
    holdings: list[Holding],
    tickers: dict[str, str],
    sectors: dict[str, str],
    prices: pd.DataFrame,
    base_currency: Currency,
    usdinr: pd.Series | None,
) -> list[ResolvedHolding]:
    """Attach ticker, sector, latest price and base-currency values to holdings.

    Holdings whose symbol has no ticker or no price column are skipped.
    """
    resolved: list[ResolvedHolding] = []
    for h in holdings:
        ticker = tickers.get(h.symbol)
        if ticker is None or ticker not in prices.columns or prices[ticker].dropna().empty:
            continue
        local = prices[ticker].dropna()
        cur = ticker_currency(ticker)
        base_px = ret.to_base_currency(local, cur, base_currency, usdinr)
        invested = None
        if h.avg_buy_price is not None:
            invested = float(h.avg_buy_price * h.quantity * (base_px.iloc[-1] / local.iloc[-1]))
        resolved.append(
            ResolvedHolding(
                **h.model_dump(),
                yahoo_ticker=ticker,
                sector=sectors.get(ticker, "Unknown"),
                latest_price=float(local.iloc[-1]),
                price_currency=cur,
                market_value=float(base_px.iloc[-1] * h.quantity),
                invested=invested,
            )
        )
    return resolved


def analyze(
    holdings: list[ResolvedHolding],
    prices: pd.DataFrame,
    benchmark_prices: pd.Series,
    benchmark_name: str,
    base_currency: Currency = "INR",
    usdinr: pd.Series | None = None,
    risk_free: float | None = None,
    warnings: list[str] | None = None,
) -> AnalysisResult:
    """Run the full analysis. `prices` has one local-currency column per Yahoo ticker."""
    warn = list(warnings or [])
    rf = default_risk_free(base_currency) if risk_free is None else risk_free
    td = settings.trading_days

    cols = [h.yahoo_ticker for h in holdings]
    cleaned, dropped = ret.clean_prices(
        prices[cols], settings.min_history_days, settings.max_ffill_days
    )
    for t in dropped:
        warn.append(f"Dropped {t}: fewer than {settings.min_history_days} days of price history.")
    kept = [h for h in holdings if h.yahoo_ticker not in dropped]
    if not kept or len(cleaned) < 2:
        raise ValueError("Not enough price history to analyze this portfolio.")

    by_ticker = {h.yahoo_ticker: h for h in kept}
    base_prices = pd.DataFrame(
        {
            t: ret.to_base_currency(cleaned[t], h.price_currency, base_currency, usdinr)
            for t, h in by_ticker.items()
        }
    )
    qty = pd.Series({t: h.quantity for t, h in by_ticker.items()})
    values = ret.portfolio_value(base_prices, qty)
    port_ret = ret.daily_returns(values)

    # Align the benchmark to the portfolio calendar so mixed-market holidays don't drop days.
    bench = benchmark_prices.sort_index()
    bench = bench.reindex(bench.index.union(values.index)).ffill().reindex(values.index)
    bench_ret = ret.daily_returns(bench.dropna())

    mv = pd.Series({h.symbol: h.market_value for h in kept})
    w = conc.weights(mv)
    sec_w = conc.sector_exposure(w, pd.Series({h.symbol: h.sector for h in kept}))

    priced = [h for h in kept if h.invested is not None]
    if len(priced) < len(kept):
        warn.append("Some holdings have no buy price; P&L covers only holdings with one.")
    pnl_value = float(sum(h.market_value for h in priced))
    invested = float(sum(h.invested or 0.0 for h in priced))
    pnl = pnl_value - invested
    summary = Summary(
        value=float(mv.sum()),
        invested=invested,
        pnl=pnl,
        pnl_pct=pnl / invested if invested else None,
        base_currency=base_currency,
    )

    metrics = RiskMetrics(
        volatility=risk.annualized_volatility(port_ret, td),
        beta=risk.beta(port_ret, bench_ret),
        sharpe=risk.sharpe_ratio(port_ret, rf, td),
        var_95=risk.historical_var(port_ret, 0.95),
        max_drawdown=dd.max_drawdown(values),
        risk_free_rate=rf,
        benchmark=benchmark_name,
        trading_days=td,
        observations=len(port_ret),
        hhi=conc.hhi(w),
        effective_n=conc.effective_n(w),
        top5_concentration=conc.top_n_concentration(w, 5),
    )

    corr = base_prices.pct_change().dropna().corr()
    corr_syms = [by_ticker[t].symbol for t in corr.columns]

    return AnalysisResult(
        summary=summary,
        weights=[
            WeightItem(symbol=s, weight=float(w[s]), market_value=float(mv[s]))
            for s in w.sort_values(ascending=False).index
        ],
        sector_exposure=[SectorExposure(sector=s, weight=float(x)) for s, x in sec_w.items()],
        risk=metrics,
        drawdown_series=[
            DrawdownPoint(date=d.strftime("%Y-%m-%d"), drawdown=float(x))
            for d, x in dd.drawdown_series(values).items()
        ],
        correlation=CorrelationMatrix(
            symbols=corr_syms, values=[[float(x) for x in row] for row in corr.to_numpy()]
        ),
        warnings=warn,
        disclaimer=DISCLAIMER,
    )
