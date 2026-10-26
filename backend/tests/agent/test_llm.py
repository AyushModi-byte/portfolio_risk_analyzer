from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.llm import (
    FakeLLM,
    GeminiLLM,
    LLMError,
    LLMResponse,
    Message,
    ToolCall,
    ToolSpec,
    _text,
    fake_json,
)


class StubChat:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result, self.error = result, error
        self.bound: list[Any] | None = None
        self.sent: list[Any] = []

    def bind_tools(self, tools: list[Any]) -> "StubChat":
        self.bound = tools
        return self

    def invoke(self, messages: list[Any]) -> Any:
        self.sent = messages
        if self.error:
            raise self.error
        return self.result


def gemini(stub: StubChat) -> GeminiLLM:
    g = GeminiLLM.__new__(GeminiLLM)  # skip the real client
    g.model = "test"
    g._chat = stub  # type: ignore[assignment]
    return g


def test_fake_llm_script_in_order_and_records_calls() -> None:
    llm = FakeLLM(["one", LLMResponse(content="two"), lambda msgs, tools: f"saw {len(msgs)}"])
    assert llm.invoke([Message("user", "a")]).content == "one"
    assert llm.invoke([]).content == "two"
    assert llm.invoke([Message("user", "a"), Message("user", "b")]).content == "saw 2"
    assert len(llm.calls) == 3
    with pytest.raises(LLMError):
        llm.invoke([])


def test_fake_json() -> None:
    assert fake_json({"a": 1}) == '{"a": 1}'


def test_text_normalises_content_blocks() -> None:
    assert _text("hi") == "hi"
    assert _text([{"type": "text", "text": "a"}, "b", {"type": "image"}]) == "ab"
    assert _text(None) == ""


def test_gemini_converts_messages_and_parses_tool_calls() -> None:
    ai = AIMessage(content="", tool_calls=[{"name": "get_summary", "args": {"n": 2}, "id": "x1"}])
    stub = StubChat(ai)
    spec = ToolSpec("get_summary", "desc", {"type": "object", "properties": {}})
    resp = gemini(stub).invoke(
        [
            Message("system", "sys"),
            Message("user", "q"),
            Message("assistant", "", [ToolCall("get_summary", {}, "x0")]),
            Message("tool", "{}", tool_call_id="x0", name="get_summary"),
        ],
        [spec],
    )
    assert [type(m) for m in stub.sent] == [SystemMessage, HumanMessage, AIMessage, ToolMessage]
    assert stub.bound == [
        {
            "type": "function",
            "function": {
                "name": "get_summary",
                "description": "desc",
                "parameters": spec.parameters,
            },
        }
    ]
    assert resp.tool_calls == [ToolCall("get_summary", {"n": 2}, "x1")]
    assert resp.raw is ai


def test_gemini_reuses_raw_assistant_message() -> None:
    raw = AIMessage(content="kept", additional_kwargs={"signature": "abc"})
    stub = StubChat(AIMessage(content="ok"))
    gemini(stub).invoke([Message("assistant", "kept", raw=raw)])
    assert stub.sent == [raw]


def test_gemini_text_reply_without_tools() -> None:
    stub = StubChat(AIMessage(content=[{"type": "text", "text": "hello"}]))
    resp = gemini(stub).invoke([Message("user", "hi")])
    assert resp.content == "hello" and resp.tool_calls == [] and stub.bound is None


def test_gemini_errors_never_leak_request_text() -> None:
    stub = StubChat(error=RuntimeError("prompt was: SECRET-PORTFOLIO-DATA"))
    with pytest.raises(LLMError) as err:
        gemini(stub).invoke([Message("user", "SECRET-PORTFOLIO-DATA")])
    assert "SECRET" not in str(err.value)
    assert "RuntimeError" in str(err.value)


class GoogleRateLimitError(Exception):
    pass


def test_gemini_rate_limit_is_its_own_error() -> None:
    from app.agent.llm import LLMRateLimitError

    with pytest.raises(LLMRateLimitError) as err:
        gemini(StubChat(error=GoogleRateLimitError("quota for SECRET"))).invoke(
            [Message("user", "q")]
        )
    assert "SECRET" not in str(err.value)
    assert isinstance(err.value, LLMError)
