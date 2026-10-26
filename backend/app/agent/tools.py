"""The fixed tool list for the chat agent.

Tools only read the AnalysisResult passed with the request (or re-run the analytics engine through
the normal pipeline for what-if). They never execute code, touch the file system or accept free
text beyond a symbol or small integer. Fractions come with matching `_percent` fields.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from app.agent.llm import ToolSpec
from app.agent.validation import TOP_N, VAR_CONFIDENCE
from app.analytics import concentration as conc
from app.analytics import correlation as cor
from app.analytics import drawdown as dd
from app.analytics import risk
from app.schemas import AnalysisResult, AnalyzeRequest
from app.services.pipeline import PipelineError, run_analysis

MAX_TOOL_CALLS = 5


@dataclass
class ToolContext:
    analysis: AnalysisResult
    request: AnalyzeRequest | None = None  # needed only for what_if_remove
    whatif_runner: Callable[[AnalyzeRequest], AnalysisResult] = run_analysis


class NoArgs(BaseModel):
    pass


class TopHoldingsArgs(BaseModel):
    n: int = Field(default=5, ge=1, le=20, description="How many holdings to return.")


class DrawdownArgs(BaseModel):
    n: int = Field(default=3, ge=1, le=10, description="How many drawdown episodes to return.")


class SymbolArgs(BaseModel):
    symbol: str = Field(min_length=1, max_length=40, description="A holding symbol.")


class OptionalSymbolArgs(BaseModel):
    symbol: str = Field(
        default="", max_length=40, description="A holding symbol, or leave empty for all holdings."
    )


def pct(x: float | None) -> float | None:
    return None if x is None else round(x * 100, 2)


def with_percent(d: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Add `<key>_percent` next to each fractional key."""
    out = dict(d)
    for k in keys:
        if k in d:
            out[f"{k}_percent"] = pct(d[k])
    return out


def find_symbol(a: AnalysisResult, symbol: str) -> str | None:
    wanted = symbol.strip().upper()
    return next((w.symbol for w in a.weights if w.symbol.upper() == wanted), None)


def _unknown(a: AnalysisResult, symbol: str) -> dict[str, Any]:
    return {"error": "symbol not found in this analysis", "symbols": [w.symbol for w in a.weights]}


# --- tools ------------------------------------------------------------------------------------


def get_summary(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    s = ctx.analysis.summary
    out = {
        "value": s.value,
        "invested": s.invested,
        "pnl": s.pnl,
        "pnl_return": s.pnl_pct,
        "base_currency": s.base_currency,
        "holdings_count": len(ctx.analysis.weights),
        "sector_count": len(ctx.analysis.sector_exposure),
    }
    return with_percent(out, "pnl_return")


def get_top_holdings(ctx: ToolContext, args: TopHoldingsArgs) -> dict[str, Any]:
    ranked = sorted(ctx.analysis.weights, key=lambda w: -w.weight)[: args.n]
    w = pd.Series({x.symbol: x.weight for x in ctx.analysis.weights})
    return {
        "n": args.n,
        "holdings": [
            with_percent(
                {"symbol": x.symbol, "weight": x.weight, "market_value": x.market_value}, "weight"
            )
            for x in ranked
        ],
        **with_percent({"combined_weight": conc.top_n_concentration(w, args.n)}, "combined_weight"),
        "holdings_count": len(ctx.analysis.weights),
    }


def get_sector_exposure(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    return {
        "sector_count": len(ctx.analysis.sector_exposure),
        "sectors": [
            with_percent({"sector": s.sector, "weight": s.weight}, "weight")
            for s in ctx.analysis.sector_exposure
        ],
    }


def get_risk_metrics(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    r = ctx.analysis.risk
    out = {
        "volatility": r.volatility,
        "beta": r.beta,
        "sharpe": r.sharpe,
        "var_95": r.var_95,
        "var_confidence": VAR_CONFIDENCE,
        "max_drawdown": r.max_drawdown,
        "risk_free_rate": r.risk_free_rate,
        "benchmark": r.benchmark,
        "hhi": r.hhi,
        "effective_n": r.effective_n,
        "top_n": TOP_N,
        "top5_concentration": r.top5_concentration,
        "observations": r.observations,
        "trading_days": r.trading_days,
    }
    return with_percent(
        out,
        "volatility",
        "var_95",
        "var_confidence",
        "max_drawdown",
        "risk_free_rate",
        "top5_concentration",
    )


def get_drawdown_periods(ctx: ToolContext, args: DrawdownArgs) -> dict[str, Any]:
    series = pd.Series(
        [p.drawdown for p in ctx.analysis.drawdown_series],
        index=pd.to_datetime([p.date for p in ctx.analysis.drawdown_series]),
    )
    episodes = dd.episodes_from_drawdown(series, args.n) if len(series) else []
    return {
        "n": args.n,
        "episodes": [with_percent(e, "depth") for e in episodes],  # type: ignore[arg-type]
        "episode_count": len(episodes),
    }


def get_correlations(ctx: ToolContext, args: OptionalSymbolArgs) -> dict[str, Any]:
    c = ctx.analysis.correlation
    if len(c.symbols) < 2:
        return {"error": "correlations need at least two holdings"}
    frame = pd.DataFrame(c.values, index=c.symbols, columns=c.symbols)
    if args.symbol:
        sym = find_symbol(ctx.analysis, args.symbol)
        if sym is None or sym not in frame.index:
            return _unknown(ctx.analysis, args.symbol)
        return cor.correlations_with(frame, sym)
    return cor.correlation_summary(frame)


def risk_contribution(ctx: ToolContext, args: OptionalSymbolArgs) -> dict[str, Any]:
    a = ctx.analysis
    if any(w.volatility is None for w in a.weights):
        return {"error": "per-holding volatility is missing from this analysis"}
    c = a.correlation
    frame = pd.DataFrame(c.values, index=c.symbols, columns=c.symbols)
    weights = pd.Series({w.symbol: w.weight for w in a.weights})
    vols = pd.Series({w.symbol: w.volatility for w in a.weights})
    if set(weights.index) != set(frame.index):
        return {"error": "correlation matrix does not cover every holding"}
    try:
        rc = risk.risk_contribution(weights, vols, frame)
    except ValueError as exc:
        return {"error": str(exc)}

    def row(sym: str) -> dict[str, Any]:
        return with_percent(
            {"symbol": sym, "weight": float(weights[sym]), "risk_contribution": float(rc[sym])},
            "weight",
            "risk_contribution",
        )

    if args.symbol:
        sym = find_symbol(a, args.symbol)
        if sym is None:
            return _unknown(a, args.symbol)
        return row(sym)
    top = rc.sort_values(ascending=False).index[:5]
    return {"holdings_count": len(rc), "top_contributors": [row(s) for s in top]}


_SNAPSHOT_FRACTIONS = ("volatility", "var_95", "max_drawdown", "top5_concentration")


def _snapshot(a: AnalysisResult) -> dict[str, Any]:
    r = a.risk
    return {
        "value": a.summary.value,
        "volatility": r.volatility,
        "beta": r.beta,
        "sharpe": r.sharpe,
        "var_95": r.var_95,
        "max_drawdown": r.max_drawdown,
        "hhi": r.hhi,
        "effective_n": r.effective_n,
        "top5_concentration": r.top5_concentration,
        "holdings_count": len(a.weights),
    }


def what_if_remove(ctx: ToolContext, args: SymbolArgs) -> dict[str, Any]:
    a = ctx.analysis
    sym = find_symbol(a, args.symbol)
    if sym is None:
        return _unknown(a, args.symbol)
    if ctx.request is None:
        return {"error": "what-if needs the original analysis request, which was not provided"}
    remaining = [h for h in ctx.request.holdings if h.symbol.upper() != sym.upper()]
    if len(remaining) == len(ctx.request.holdings):
        return {"error": "symbol is not part of the original request"}
    if not remaining:
        return {"error": "cannot remove the only holding"}
    # Pin the benchmark so the comparison is like for like.
    new_request = ctx.request.model_copy(
        update={"holdings": remaining, "benchmark": a.risk.benchmark}
    )
    try:
        after = ctx.whatif_runner(new_request)
    except (PipelineError, ValueError) as exc:
        return {"error": f"re-running the analysis failed: {exc}"}
    before_s, after_s = _snapshot(a), _snapshot(after)
    change = {
        k: (after_s[k] - before_s[k])
        if before_s[k] is not None and after_s[k] is not None
        else None
        for k in before_s
    }
    removed_weight = next(w.weight for w in a.weights if w.symbol == sym)
    fractions = _SNAPSHOT_FRACTIONS
    return {
        "removed": sym,
        "removed_weight": removed_weight,
        "removed_weight_percent": pct(removed_weight),
        "before": with_percent(before_s, *fractions),
        "after": with_percent(after_s, *fractions),
        "change": with_percent(change, *fractions),
        "change_note": "change = after minus before; _percent fields are percentage points",
    }


# --- registry ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[ToolContext, Any], dict[str, Any]]


TOOLS: list[Tool] = [
    Tool("get_summary", "Portfolio value, invested amount, P&L and counts.", NoArgs, get_summary),
    Tool(
        "get_top_holdings",
        "Largest holdings by weight, with their combined weight.",
        TopHoldingsArgs,
        get_top_holdings,
    ),
    Tool("get_sector_exposure", "Portfolio weight in each sector.", NoArgs, get_sector_exposure),
    Tool(
        "get_risk_metrics",
        "Volatility, beta, Sharpe, 1-day VaR, max drawdown, HHI, effective N, top-5 concentration.",
        NoArgs,
        get_risk_metrics,
    ),
    Tool(
        "get_drawdown_periods",
        "The deepest drawdown episodes with peak, trough and recovery dates.",
        DrawdownArgs,
        get_drawdown_periods,
    ),
    Tool(
        "get_correlations",
        "Average pairwise correlation and the most and least correlated pairs, or one holding's "
        "correlations with the others.",
        OptionalSymbolArgs,
        get_correlations,
    ),
    Tool(
        "risk_contribution",
        "Share of portfolio risk (variance) contributed by one holding, or the top contributors "
        "when no symbol is given.",
        OptionalSymbolArgs,
        risk_contribution,
    ),
    Tool(
        "what_if_remove",
        "Re-run the analytics without one holding and compare risk metrics before and after.",
        SymbolArgs,
        what_if_remove,
    ),
]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def tool_specs() -> list[ToolSpec]:
    specs = []
    for t in TOOLS:
        schema = t.args_model.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        specs.append(ToolSpec(name=t.name, description=t.description, parameters=schema))
    return specs


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one tool by name. Unknown tools and bad arguments return an error dict."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return {"error": "unknown tool", "tools": sorted(TOOLS_BY_NAME)}
    try:
        parsed = tool.args_model(**(args or {}))
    except (ValidationError, TypeError) as exc:
        detail = (
            "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
            if isinstance(exc, ValidationError)
            else "invalid arguments"
        )
        return {"error": f"invalid arguments ({detail})"}
    return tool.fn(ctx, parsed)
