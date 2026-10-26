"""LLM access behind a tiny interface, so graphs and tests never depend on a vendor SDK."""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, Protocol

from app.config import settings

# Stable Flash model that Google lists as free of charge on the standard tier (ai.google.dev
# pricing). gemini-3.8-flash is newer but timed out with a 504 in testing, so the default is
# gemini-3.6-flash. Override with GEMINI_MODEL.
DEFAULT_MODEL = "gemini-3.6-flash"
REQUEST_TIMEOUT_SECONDS = 45


class AIUnavailableError(RuntimeError):
    """No API key is configured; AI features are switched off."""


class LLMError(RuntimeError):
    """The model call failed or returned something unusable."""


class LLMRateLimitError(LLMError):
    """The provider rejected the call for quota or rate reasons; retrying later may work."""


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    id: str = ""


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""
    raw: Any = None  # vendor message kept so provider metadata survives the next turn


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


class LLM(Protocol):
    def invoke(self, messages: list[Message], tools: list[ToolSpec] | None = None) -> LLMResponse:
        """Return the model's next message. Raises LLMError on failure."""
        ...


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


class GeminiLLM:
    def __init__(self, api_key: str, model: str, temperature: float = 0.2) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.model = model
        self._chat = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=2,
        )

    @staticmethod
    def _convert(messages: list[Message]) -> list[Any]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

        out: list[Any] = []
        for m in messages:
            if m.role == "system":
                out.append(SystemMessage(content=m.content))
            elif m.role == "user":
                out.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                if m.raw is not None:
                    out.append(m.raw)
                else:
                    calls = [{"name": c.name, "args": c.args, "id": c.id} for c in m.tool_calls]
                    out.append(AIMessage(content=m.content, tool_calls=calls))
            else:
                out.append(ToolMessage(content=m.content, tool_call_id=m.tool_call_id, name=m.name))
        return out

    def invoke(self, messages: list[Message], tools: list[ToolSpec] | None = None) -> LLMResponse:
        chat: Any = self._chat
        if tools:
            specs = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
            chat = chat.bind_tools(specs)
        try:
            ai = chat.invoke(self._convert(messages))
        except Exception as exc:
            # Type only: exception text can echo request content.
            name = type(exc).__name__
            if "ratelimit" in name.lower() or "resourceexhausted" in name.lower():
                raise LLMRateLimitError(
                    "The AI service is rate limited; try again shortly."
                ) from exc
            raise LLMError(f"Model call failed ({name}).") from exc
        calls = [
            ToolCall(name=c["name"], args=dict(c.get("args") or {}), id=str(c.get("id") or ""))
            for c in (getattr(ai, "tool_calls", None) or [])
        ]
        return LLMResponse(content=_text(ai.content), tool_calls=calls, raw=ai)


ScriptItem = LLMResponse | str | Callable[[list[Message], list[ToolSpec] | None], LLMResponse | str]


class FakeLLM:
    """Scripted LLM for tests and offline evals. Each invoke consumes one script item."""

    def __init__(self, script: Iterable[ScriptItem]) -> None:
        self._script = list(script)
        self.calls: list[tuple[list[Message], list[ToolSpec] | None]] = []

    def invoke(self, messages: list[Message], tools: list[ToolSpec] | None = None) -> LLMResponse:
        self.calls.append((list(messages), tools))
        if not self._script:
            raise LLMError("FakeLLM script exhausted.")
        item = self._script.pop(0)
        if callable(item):
            item = item(messages, tools)
        return LLMResponse(content=item) if isinstance(item, str) else item


def fake_tool_call(name: str, **args: Any) -> LLMResponse:
    return LLMResponse(tool_calls=[ToolCall(name=name, args=args, id=f"call-{name}")])


def fake_json(payload: Any) -> str:
    return json.dumps(payload)


@lru_cache(maxsize=2)
def _build_gemini(api_key: str, model: str) -> GeminiLLM:
    return GeminiLLM(api_key, model)


def get_llm() -> LLM | None:
    """The configured model, or None when no key is set (AI features report 'AI unavailable')."""
    if not settings.gemini_api_key.strip():
        return None
    return _build_gemini(
        settings.gemini_api_key.strip(), settings.gemini_model.strip() or DEFAULT_MODEL
    )
