from typing import Any

import pytest

from app.agent import tools as t
from app.schemas import AnalysisResult, AnalyzeRequest
from app.services.pipeline import PipelineError, run_analysis


@pytest.fixture
def ctx(analysis: AnalysisResult, mixed_request: AnalyzeRequest) -> t.ToolContext:
    return t.ToolContext(analysis=analysis, request=mixed_request)


def call(ctx: t.ToolContext, name: str, **args: Any) -> dict[str, Any]:
    return t.run_tool(ctx, name, args)


def test_registry_is_the_fixed_list_with_safe_arguments() -> None:
    assert [x.name for x in t.TOOLS] == [
        "get_summary",
        "get_top_holdings",
        "get_sector_exposure",
        "get_risk_metrics",
        "get_drawdown_periods",
        "get_correlations",
        "risk_contribution",
        "what_if_remove",
    ]
    arg_names = {p for spec in t.tool_specs() for p in spec.parameters.get("properties", {})}
    assert arg_names == {"n", "symbol"}  # no free-form text, code or paths
    for spec in t.tool_specs():
        assert "title" not in spec.parameters
        assert spec.parameters["type"] == "object"


def test_get_summary(ctx: t.ToolContext) -> None:
    out = call(ctx, "get_summary")
    s = ctx.analysis.summary
    assert out["value"] == s.value and out["invested"] == s.invested and out["pnl"] == s.pnl
    assert out["pnl_return_percent"] == round(s.pnl_pct * 100, 2)  # type: ignore[operator]
    assert out["holdings_count"] == len(ctx.analysis.weights)
    assert out["base_currency"] == "INR"


def test_get_top_holdings(ctx: t.ToolContext) -> None:
    out = call(ctx, "get_top_holdings", n=3)
    ranked = sorted(ctx.analysis.weights, key=lambda w: -w.weight)
    assert [h["symbol"] for h in out["holdings"]] == [w.symbol for w in ranked[:3]]
    assert out["n"] == 3
    assert out["combined_weight"] == pytest.approx(sum(w.weight for w in ranked[:3]), abs=1e-12)
    assert out["holdings"][0]["weight_percent"] == round(ranked[0].weight * 100, 2)
    assert call(ctx, "get_top_holdings")["n"] == 5  # default


def test_get_sector_exposure(ctx: t.ToolContext) -> None:
    out = call(ctx, "get_sector_exposure")
    assert out["sector_count"] == len(out["sectors"]) >= 5
    assert sum(s["weight"] for s in out["sectors"]) == pytest.approx(1.0, abs=1e-9)


def test_get_risk_metrics(ctx: t.ToolContext) -> None:
    out = call(ctx, "get_risk_metrics")
    r = ctx.analysis.risk
    assert out["volatility"] == r.volatility
    assert out["volatility_percent"] == round(r.volatility * 100, 2)
    assert out["beta"] == r.beta and out["sharpe"] == r.sharpe
    assert out["var_confidence_percent"] == 95.0
    assert out["top_n"] == 5
    assert out["benchmark"] == r.benchmark


def test_get_drawdown_periods_deepest_matches_max_drawdown(ctx: t.ToolContext) -> None:
    out = call(ctx, "get_drawdown_periods", n=3)
    eps = out["episodes"]
    assert 1 <= len(eps) <= 3 and out["episode_count"] == len(eps)
    assert eps[0]["depth"] == pytest.approx(ctx.analysis.risk.max_drawdown, abs=1e-12)
    assert [e["depth"] for e in eps] == sorted(e["depth"] for e in eps)
    assert eps[0]["peak_date"] <= eps[0]["trough_date"]


def test_get_correlations(ctx: t.ToolContext) -> None:
    out = call(ctx, "get_correlations")
    n = len(ctx.analysis.weights)
    assert out["pair_count"] == n * (n - 1) // 2
    assert out["most_correlated"][0]["correlation"] >= out["least_correlated"][0]["correlation"]
    one = call(ctx, "get_correlations", symbol="tcs")  # case-insensitive
    assert one["symbol"] == "TCS" and len(one["highest"]) == 3


def test_get_correlations_unknown_symbol_and_single_holding(ctx: t.ToolContext) -> None:
    assert call(ctx, "get_correlations", symbol="NOPE")["error"].startswith("symbol not found")
    single = ctx.analysis.model_copy(
        update={
            "correlation": ctx.analysis.correlation.model_copy(
                update={"symbols": ["A"], "values": [[1.0]]}
            )
        }
    )
    out = t.run_tool(t.ToolContext(analysis=single), "get_correlations", {})
    assert "error" in out


def test_risk_contribution_sums_to_one(ctx: t.ToolContext) -> None:
    total = sum(
        call(ctx, "risk_contribution", symbol=w.symbol)["risk_contribution"]
        for w in ctx.analysis.weights
    )
    assert total == pytest.approx(1.0, abs=1e-9)
    one = call(ctx, "risk_contribution", symbol="RELIANCE")
    assert one["symbol"] == "RELIANCE"
    assert one["risk_contribution_percent"] == round(one["risk_contribution"] * 100, 2)


def test_risk_contribution_top_contributors(ctx: t.ToolContext) -> None:
    out = call(ctx, "risk_contribution")
    contribs = [c["risk_contribution"] for c in out["top_contributors"]]
    assert contribs == sorted(contribs, reverse=True) and len(contribs) == 5


def test_risk_contribution_errors(ctx: t.ToolContext) -> None:
    assert "error" in call(ctx, "risk_contribution", symbol="NOPE")
    stripped = ctx.analysis.model_copy(
        update={
            "weights": [w.model_copy(update={"volatility": None}) for w in ctx.analysis.weights]
        }
    )
    assert "error" in t.run_tool(t.ToolContext(analysis=stripped), "risk_contribution", {})


def test_what_if_remove_with_fake_runner_pins_benchmark(ctx: t.ToolContext) -> None:
    seen: list[AnalyzeRequest] = []

    def runner(req: AnalyzeRequest) -> AnalysisResult:
        seen.append(req)
        return run_analysis(req)

    ctx.whatif_runner = runner
    out = call(ctx, "what_if_remove", symbol="tcs")
    assert out["removed"] == "TCS"
    assert "TCS" not in {h.symbol for h in seen[0].holdings}
    assert len(seen[0].holdings) == len(ctx.request.holdings) - 1  # type: ignore[union-attr]
    assert seen[0].benchmark == ctx.analysis.risk.benchmark
    assert out["before"]["holdings_count"] == len(ctx.analysis.weights)
    assert out["after"]["holdings_count"] == len(ctx.analysis.weights) - 1
    for k in ("volatility", "beta", "max_drawdown"):
        assert out["change"][k] == pytest.approx(out["after"][k] - out["before"][k], abs=1e-12)
    assert out["change"]["volatility_percent"] == round(out["change"]["volatility"] * 100, 2)


def test_what_if_remove_errors(ctx: t.ToolContext) -> None:
    assert call(ctx, "what_if_remove", symbol="NOPE")["error"].startswith("symbol not found")
    no_request = t.ToolContext(analysis=ctx.analysis)
    assert (
        "original analysis request"
        in t.run_tool(no_request, "what_if_remove", {"symbol": "TCS"})["error"]
    )

    def failing(_: AnalyzeRequest) -> AnalysisResult:
        raise PipelineError("boom")

    ctx.whatif_runner = failing
    assert "re-running the analysis failed" in call(ctx, "what_if_remove", symbol="TCS")["error"]

    only = ctx.request.model_copy(
        update={"holdings": [h for h in ctx.request.holdings if h.symbol == "TCS"]}
    )  # type: ignore[union-attr]
    assert (
        "only holding"
        in t.run_tool(
            t.ToolContext(analysis=ctx.analysis, request=only), "what_if_remove", {"symbol": "TCS"}
        )["error"]
    )

    other = ctx.request.model_copy(
        update={"holdings": [h for h in ctx.request.holdings if h.symbol != "TCS"]}
    )  # type: ignore[union-attr]
    assert (
        "not part of the original request"
        in t.run_tool(
            t.ToolContext(analysis=ctx.analysis, request=other), "what_if_remove", {"symbol": "TCS"}
        )["error"]
    )


def test_run_tool_rejects_unknown_tool_and_bad_arguments(ctx: t.ToolContext) -> None:
    assert call(ctx, "delete_everything")["error"] == "unknown tool"
    assert call(ctx, "exec", code="print(1)")["error"] == "unknown tool"
    assert "invalid arguments" in call(ctx, "get_top_holdings", n=0)["error"]
    assert "invalid arguments" in call(ctx, "get_top_holdings", n=999)["error"]
    assert "invalid arguments" in call(ctx, "get_top_holdings", n="ten")["error"]
    assert "invalid arguments" in call(ctx, "what_if_remove")["error"]
    assert "invalid arguments" in call(ctx, "what_if_remove", symbol="x" * 100)["error"]


def test_tool_module_does_not_import_code_execution_or_filesystem_helpers() -> None:
    import inspect

    source = inspect.getsource(t)
    for banned in ("subprocess", "eval(", "exec(", "open(", "os.system", "pathlib", "import os"):
        assert banned not in source
