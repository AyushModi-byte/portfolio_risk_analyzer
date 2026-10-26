"""Insights built in code, used when no model is available or its output fails validation."""

from app.agent.models import Insight
from app.agent.validation import display_value, metric_index
from app.schemas import AnalysisResult


def template_insights(a: AnalysisResult) -> list[Insight]:
    m = metric_index(a)
    cur = a.summary.base_currency

    def d(key: str) -> str:
        return display_value(key, m[key], cur)

    out: list[Insight] = []
    if a.weights:
        top = max(a.weights, key=lambda w: w.weight)
        out.append(
            Insight(
                text=(
                    f"The largest holding is {top.symbol} at {d(f'weight.{top.symbol}')} of the "
                    f"portfolio, and the top {d('param.top_n')} holdings together make up "
                    f"{d('risk.top5_concentration')}."
                ),
                metric_keys=[f"weight.{top.symbol}", "param.top_n", "risk.top5_concentration"],
            )
        )
        out.append(
            Insight(
                text=(
                    f"The portfolio behaves like {d('risk.effective_n')} equal-sized holdings "
                    f"although it contains {d('count.holdings')} positions (HHI {d('risk.hhi')})."
                ),
                metric_keys=["risk.effective_n", "count.holdings", "risk.hhi"],
            )
        )
    if a.sector_exposure:
        sector = max(a.sector_exposure, key=lambda s: s.weight)
        out.append(
            Insight(
                text=(
                    f"The largest sector is {sector.sector} at {d(f'sector.{sector.sector}')} of "
                    f"the portfolio, across {d('count.sectors')} sectors in total."
                ),
                metric_keys=[f"sector.{sector.sector}", "count.sectors"],
            )
        )
    out.append(
        Insight(
            text=(
                f"Annualized volatility over the window is {d('risk.volatility')}. Historical "
                f"value at risk at {d('param.var_confidence')} confidence is {d('risk.var_95')} "
                "of portfolio value in one day."
            ),
            metric_keys=["risk.volatility", "param.var_confidence", "risk.var_95"],
        )
    )
    out.append(
        Insight(
            text=(
                f"The deepest peak-to-trough fall in the window was {d('risk.max_drawdown')}. "
                "This describes how today's holdings would have behaved, not what you earned."
            ),
            metric_keys=["risk.max_drawdown"],
        )
    )
    if "risk.beta" in m and "risk.sharpe" in m:
        out.append(
            Insight(
                text=(
                    f"Beta against {a.risk.benchmark} is {d('risk.beta')} and the Sharpe ratio is "
                    f"{d('risk.sharpe')}."
                ),
                metric_keys=["risk.beta", "risk.sharpe"],
            )
        )
    if len(out) < 6 and "summary.pnl_pct" in m:
        out.append(
            Insight(
                text=(
                    f"Current value is {d('summary.value')} against {d('summary.invested')} "
                    f"invested, a return of {d('summary.pnl_pct')}."
                ),
                metric_keys=["summary.value", "summary.invested", "summary.pnl_pct"],
            )
        )
    return out[:6]
