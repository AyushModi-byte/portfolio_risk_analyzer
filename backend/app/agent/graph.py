"""The three LangGraph flows: mapping assistant, insight writer and Q&A agent.

The model only words things and picks tools. Numbers come from the analytics code, and every
model output is validated before it is returned.
"""

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agent import prompts
from app.agent.llm import LLM, LLMError, LLMResponse, Message
from app.agent.models import ChatResult, Insight, InsightsResult, MappingResult, ToolRecord
from app.agent.templates import template_insights
from app.agent.tools import MAX_TOOL_CALLS, ToolContext, run_tool, tool_specs
from app.agent.validation import (
    contains_advice,
    is_advice_request,
    metric_index,
    numbers_in_payload,
    prompt_metrics,
    symbol_terms,
    unsupported_numbers,
)
from app.schemas import DISCLAIMER, AnalysisResult

UNVERIFIED_ANSWER = (
    "I couldn't produce an answer I could verify against the computed analysis, so I won't "
    "guess. Try asking about a specific metric, such as volatility or the top holdings. "
    f"{DISCLAIMER}"
)
MAX_ATTEMPTS = 2  # first try plus one regeneration


def extract_json(text: str) -> Any | None:
    """Parse the first JSON object in a model reply, tolerating markdown fences."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except ValueError:
        return None


# --- insight writer ---------------------------------------------------------------------------


def validate_insights(raw: Any, analysis: AnalysisResult) -> tuple[list[Insight], list[str]]:
    """Check shape, cited keys, advice and each number (within rounding): (insights, errors)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("insights"), list):
        return [], ['Reply must be JSON like {"insights": [{"text": ..., "metric_keys": [...]}]}.']
    items = raw["insights"]
    errors: list[str] = []
    if not 4 <= len(items) <= 6:
        errors.append(f"Write between 4 and 6 insights (you wrote {len(items)}).")
    index = metric_index(analysis)
    terms = symbol_terms(analysis)
    insights: list[Insight] = []
    for i, item in enumerate(items, start=1):
        label = f"Insight {i}"
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            errors.append(f"{label} needs a text string.")
            continue
        text = item["text"].strip()
        keys = item.get("metric_keys")
        if not text or len(text) > 500:
            errors.append(f"{label} text must be 1 to 500 characters.")
            continue
        if not isinstance(keys, list) or not keys or not all(isinstance(k, str) for k in keys):
            errors.append(f"{label} must cite at least one metric key in metric_keys.")
            continue
        bad_keys = [k for k in keys if k not in index]
        if bad_keys:
            errors.append(f"{label} cites unknown metric keys: {', '.join(bad_keys[:3])}.")
            continue
        if contains_advice(text, terms):
            errors.append(f"{label} reads as advice; describe the metrics instead.")
        bad = unsupported_numbers(text, [index[k] for k in keys], terms)
        if bad:
            errors.append(
                f"{label} has numbers not found in its cited metrics: {', '.join(bad[:4])}."
            )
        insights.append(Insight(text=text, metric_keys=keys))
    return insights, errors


class InsightState(TypedDict, total=False):
    attempt: int
    raw_reply: str
    insights: list[Insight]
    errors: list[str]
    llm_failed: bool
    done: bool


def build_insight_graph(llm: LLM, analysis: AnalysisResult) -> Any:
    data = {
        "base_currency": analysis.summary.base_currency,
        "benchmark": analysis.risk.benchmark,
        "metrics": prompt_metrics(analysis),
    }
    base = [
        Message("system", prompts.INSIGHT_SYSTEM),
        Message("user", prompts.wrap_untrusted(json.dumps(data))),
    ]

    def generate(state: InsightState) -> InsightState:
        messages = list(base)
        if state.get("errors") and state.get("raw_reply") is not None:
            problems = "\n".join(f"- {e}" for e in state["errors"])
            messages += [
                Message("assistant", state["raw_reply"]),
                Message(
                    "user",
                    f"Your reply had these problems:\n{problems}\nReturn corrected JSON only.",
                ),
            ]
        attempt = state.get("attempt", 0) + 1
        try:
            reply = llm.invoke(messages).content
        except LLMError:
            return {"attempt": attempt, "llm_failed": True, "errors": ["model call failed"]}
        return {"attempt": attempt, "raw_reply": reply}

    def validate(state: InsightState) -> InsightState:
        if state.get("llm_failed"):
            return {}
        insights, errors = validate_insights(extract_json(state["raw_reply"]), analysis)
        return {"insights": insights, "errors": errors, "done": not errors}

    def route(state: InsightState) -> str:
        if state.get("done"):
            return "done"
        if state.get("llm_failed") or state.get("attempt", 0) >= MAX_ATTEMPTS:
            return "fallback"
        return "retry"

    def fallback(state: InsightState) -> InsightState:
        return {"insights": template_insights(analysis), "done": False}

    g = StateGraph(InsightState)
    g.add_node("generate", generate)
    g.add_node("validate", validate)
    g.add_node("fallback", fallback)
    g.set_entry_point("generate")
    g.add_edge("generate", "validate")
    g.add_conditional_edges(
        "validate", route, {"done": END, "retry": "generate", "fallback": "fallback"}
    )
    g.add_edge("fallback", END)
    return g.compile()


def write_insights(analysis: AnalysisResult, llm: LLM | None) -> InsightsResult:
    """Validated model insights, or template insights when there is no model or it fails twice."""
    if llm is None:
        return InsightsResult(
            insights=template_insights(analysis),
            source="template",
            note="AI unavailable; showing template insights.",
        )
    state: InsightState = build_insight_graph(llm, analysis).invoke({"attempt": 0})
    if state.get("done"):
        return InsightsResult(insights=state["insights"], source="llm", attempts=state["attempt"])
    note = (
        "The model call failed; showing template insights."
        if state.get("llm_failed")
        else "Model insights failed number validation; showing template insights."
    )
    return InsightsResult(
        insights=state["insights"], source="template", attempts=state["attempt"], note=note
    )


# --- Q&A agent --------------------------------------------------------------------------------


class QAState(TypedDict, total=False):
    messages: list[Message]
    records: list[ToolRecord]
    used: int
    repairs: int
    forced: bool
    answer: str
    verified: bool
    note: str | None
    finished: bool
    wants_tools: bool


def build_qa_graph(llm: LLM, ctx: ToolContext, question: str) -> Any:
    specs = tool_specs()
    terms = symbol_terms(ctx.analysis)

    def guard(state: QAState) -> QAState:
        if is_advice_request(question):
            return {
                "answer": prompts.ADVICE_REFUSAL,
                "verified": True,
                "note": "advice request declined",
                "finished": True,
            }
        return {"finished": False}

    def after_guard(state: QAState) -> str:
        return "end" if state.get("finished") else "agent"

    def agent(state: QAState) -> QAState:
        tools_open = not state.get("forced") and state.get("used", 0) < MAX_TOOL_CALLS
        resp: LLMResponse = llm.invoke(state["messages"], specs if tools_open else None)
        msg = Message("assistant", resp.content, resp.tool_calls, raw=resp.raw)
        return {
            "messages": [*state["messages"], msg],
            "answer": resp.content,
            "wants_tools": bool(resp.tool_calls) and tools_open,
        }

    def after_agent(state: QAState) -> str:
        return "tools" if state.get("wants_tools") else "check"

    def tools(state: QAState) -> QAState:
        messages = list(state["messages"])
        records = list(state.get("records", []))
        used = state.get("used", 0)
        for call in messages[-1].tool_calls:
            if used < MAX_TOOL_CALLS:
                output = run_tool(ctx, call.name, call.args)
                records.append(ToolRecord(name=call.name, args=call.args, output=output))
                used += 1
            else:
                output = {"error": "tool call budget exhausted"}
            messages.append(
                Message(
                    "tool", json.dumps(output, default=str), tool_call_id=call.id, name=call.name
                )
            )
        update: QAState = {"messages": messages, "records": records, "used": used}
        if used >= MAX_TOOL_CALLS:
            update["forced"] = True
            messages.append(
                Message(
                    "user", "No more tool calls are allowed. Answer now using the tool results."
                )
            )
        return update

    def check(state: QAState) -> QAState:
        answer = (state.get("answer") or "").strip()
        errors: list[str] = []
        if not answer:
            errors.append("The answer was empty.")
        if contains_advice(answer, terms):
            errors.append("The answer reads as advice; describe the analysis only.")
        allowed = numbers_in_payload([[r.args, r.output] for r in state.get("records", [])])
        bad = unsupported_numbers(answer, allowed, terms)
        if bad:
            errors.append(
                f"These numbers are not in the tool outputs: {', '.join(bad[:5])}. "
                "Use only numbers from tool results, or call a tool to get them."
            )
        if not errors:
            return {"answer": answer, "verified": True, "finished": True}
        if state.get("repairs", 0) < 1:
            feedback = "Problems with your answer:\n" + "\n".join(f"- {e}" for e in errors)
            return {
                "messages": [*state["messages"], Message("user", feedback)],
                "repairs": state.get("repairs", 0) + 1,
                "finished": False,
            }
        advice = contains_advice(answer, terms)
        return {
            "answer": prompts.ADVICE_REFUSAL if advice else UNVERIFIED_ANSWER,
            "verified": False,
            "note": "answer blocked by validation" if advice else "answer failed number validation",
            "finished": True,
        }

    def after_check(state: QAState) -> str:
        return "end" if state.get("finished") else "agent"

    g = StateGraph(QAState)
    g.add_node("guard", guard)
    g.add_node("agent", agent)
    g.add_node("tools", tools)
    g.add_node("check", check)
    g.set_entry_point("guard")
    g.add_conditional_edges("guard", after_guard, {"end": END, "agent": "agent"})
    g.add_conditional_edges("agent", after_agent, {"tools": "tools", "check": "check"})
    g.add_edge("tools", "agent")
    g.add_conditional_edges("check", after_check, {"end": END, "agent": "agent"})
    return g.compile()


def answer_question(llm: LLM, ctx: ToolContext, history: list[tuple[str, str]]) -> ChatResult:
    """Answer the last user message in `history` (list of (role, content))."""
    question = history[-1][1]
    messages = [Message("system", prompts.QA_SYSTEM)] + [
        Message("user" if role == "user" else "assistant", content) for role, content in history
    ]
    state: QAState = build_qa_graph(llm, ctx, question).invoke(
        {"messages": messages, "records": [], "used": 0, "repairs": 0},
        {"recursion_limit": 40},
    )
    return ChatResult(
        answer=state["answer"],
        tool_calls=state.get("records", []),
        verified=state.get("verified", False),
        note=state.get("note"),
    )


# --- mapping assistant ------------------------------------------------------------------------

MAPPING_FIELDS = ("symbol", "quantity", "avg_buy_price", "name", "exchange", "currency")


def validate_mapping(raw: Any, headers: list[str]) -> tuple[dict[str, str] | None, list[str]]:
    mapping = raw.get("mapping") if isinstance(raw, dict) else None
    if not isinstance(mapping, dict):
        return None, ['Reply must be JSON like {"mapping": {"symbol": "<header>", ...}}.']
    errors: list[str] = []
    clean: dict[str, str] = {}
    for field, header in mapping.items():
        if field not in MAPPING_FIELDS:
            errors.append(f"Unknown field {field!r}.")
        elif header is None:
            continue
        elif not isinstance(header, str) or header not in headers:
            errors.append(f"{field} must be one of the exact headers or null.")
        else:
            clean[field] = header
    for required in ("symbol", "quantity"):
        if required not in clean:
            errors.append(f"{required} is required and must be an exact header.")
    if len(set(clean.values())) != len(clean):
        errors.append("Each header can be used for only one field.")
    return (None, errors) if errors else (clean, [])


class MappingState(TypedDict, total=False):
    attempt: int
    raw_reply: str
    mapping: dict[str, str]
    errors: list[str]
    llm_failed: bool
    done: bool


def build_mapping_graph(llm: LLM, headers: list[str], rows: list[dict[str, str]]) -> Any:
    payload = json.dumps({"headers": headers, "sample_rows": rows})
    base = [
        Message("system", prompts.MAPPING_SYSTEM),
        Message("user", prompts.wrap_untrusted(payload)),
    ]

    def propose(state: MappingState) -> MappingState:
        messages = list(base)
        if state.get("errors") and state.get("raw_reply") is not None:
            problems = "\n".join(f"- {e}" for e in state["errors"])
            messages += [
                Message("assistant", state["raw_reply"]),
                Message("user", f"Problems:\n{problems}\nReturn corrected JSON only."),
            ]
        attempt = state.get("attempt", 0) + 1
        try:
            return {"attempt": attempt, "raw_reply": llm.invoke(messages).content}
        except LLMError:
            return {"attempt": attempt, "llm_failed": True, "errors": ["model call failed"]}

    def validate(state: MappingState) -> MappingState:
        if state.get("llm_failed"):
            return {}
        mapping, errors = validate_mapping(extract_json(state["raw_reply"]), headers)
        return {"mapping": mapping or {}, "errors": errors, "done": not errors}

    def route(state: MappingState) -> str:
        if state.get("done") or state.get("llm_failed") or state.get("attempt", 0) >= MAX_ATTEMPTS:
            return "end"
        return "retry"

    g = StateGraph(MappingState)
    g.add_node("propose", propose)
    g.add_node("validate", validate)
    g.set_entry_point("propose")
    g.add_edge("propose", "validate")
    g.add_conditional_edges("validate", route, {"end": END, "retry": "propose"})
    return g.compile()


def suggest_mapping(llm: LLM, headers: list[str], rows: list[dict[str, str]]) -> MappingResult:
    """Model-proposed column mapping, validated against the headers; the user confirms it."""
    state: MappingState = build_mapping_graph(llm, headers, rows).invoke({"attempt": 0})
    if state.get("done"):
        return MappingResult(mapping=state["mapping"], source="llm")
    reason = "model call failed" if state.get("llm_failed") else "; ".join(state.get("errors", []))
    return MappingResult(mapping=None, source="none", error=reason)
