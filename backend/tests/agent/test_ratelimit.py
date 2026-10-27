import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.agent.llm import FakeLLM, LLMRateLimitError, Message, fake_tool_call, get_llm
from app.agent.templates import template_insights
from app.config import settings
from app.main import app
from app.ratelimit import DailyBudget, SlidingWindow
from app.schemas import AnalysisResult

from .test_api_agent import chat_body


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# --- primitives -------------------------------------------------------------------------------


def test_sliding_window_allows_then_blocks_then_recovers() -> None:
    clock = Clock()
    w = SlidingWindow(clock=clock)
    assert [w.hit("a", 3, 60) for _ in range(3)] == [None, None, None]
    wait = w.hit("a", 3, 60)
    assert wait is not None and 59 <= wait <= 61
    clock.now += 30
    assert w.hit("a", 3, 60) is not None  # still inside the window
    clock.now += 31
    assert w.hit("a", 3, 60) is None  # oldest events aged out


def test_sliding_window_keys_are_independent() -> None:
    w = SlidingWindow(clock=Clock())
    assert w.hit("a", 1, 60) is None
    assert w.hit("a", 1, 60) is not None
    assert w.hit("b", 1, 60) is None


def test_sliding_window_bounds_memory() -> None:
    clock = Clock()
    w = SlidingWindow(max_keys=3, clock=clock)
    for key in "abc":
        w.hit(key, 5, 60)
    clock.now += 120  # all three are stale
    w.hit("d", 5, 60)
    assert len(w._events) == 1
    for key in "efg":
        w.hit(key, 5, 600)
    w.hit("h", 5, 600)  # nothing stale: the oldest key is dropped
    assert len(w._events) <= 3


def test_daily_budget_resets_after_a_day() -> None:
    clock = Clock()
    b = DailyBudget(clock=clock)
    assert b.charge(2) is None and b.charge(2) is None
    wait = b.charge(2)
    assert wait is not None and wait > 86000
    clock.now += 86401
    assert b.charge(2) is None


# --- client address ---------------------------------------------------------------------------


class FakeRequest:
    def __init__(self, forwarded: str | None, host: str | None = "10.0.0.1") -> None:
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}
        self.client = type("C", (), {"host": host})() if host else None


def test_client_key_uses_the_entry_the_trusted_proxy_appended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert ratelimit.client_key(FakeRequest("6.6.6.6, 9.9.9.9")) == "9.9.9.9"  # type: ignore[arg-type]
    assert ratelimit.client_key(FakeRequest("9.9.9.9")) == "9.9.9.9"  # type: ignore[arg-type]
    assert ratelimit.client_key(FakeRequest(None)) == "10.0.0.1"  # type: ignore[arg-type]
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert ratelimit.client_key(FakeRequest("1.1.1.1, 2.2.2.2, 3.3.3.3")) == "2.2.2.2"  # type: ignore[arg-type]
    assert ratelimit.client_key(FakeRequest("3.3.3.3")) == "10.0.0.1"  # fewer hops than trusted


def test_client_key_ignores_forwarded_header_when_no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    assert ratelimit.client_key(FakeRequest("6.6.6.6")) == "10.0.0.1"  # type: ignore[arg-type]
    assert ratelimit.client_key(FakeRequest(None, host=None)) == "unknown"  # type: ignore[arg-type]


# --- endpoints --------------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")  # switches the guard on
    monkeypatch.setattr(settings, "ai_requests_per_minute", 3)
    monkeypatch.setattr(settings, "ai_requests_per_day", 100)
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_llm(llm: Any) -> None:
    app.dependency_overrides[get_llm] = lambda: llm


def question(analysis: AnalysisResult, who: str = "9.9.9.9") -> Any:
    return {
        "json": chat_body(analysis, None, ("user", "Should I sell TCS?")),
        "headers": {"X-Forwarded-For": who},
    }


def test_chat_is_limited_per_client_with_retry_after(
    client: TestClient, analysis: AnalysisResult
) -> None:
    use_llm(FakeLLM([]))
    codes = [client.post("/api/chat", **question(analysis)).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    r = client.post("/api/chat", **question(analysis))
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"
    assert 1 <= int(r.headers["retry-after"]) <= 61


def test_other_clients_are_not_affected(client: TestClient, analysis: AnalysisResult) -> None:
    use_llm(FakeLLM([]))
    for _ in range(4):
        client.post("/api/chat", **question(analysis, "9.9.9.9"))
    assert client.post("/api/chat", **question(analysis, "8.8.8.8")).status_code == 200


def test_spoofed_forwarded_for_prefix_does_not_evade_the_limit(
    client: TestClient, analysis: AnalysisResult
) -> None:
    use_llm(FakeLLM([]))
    codes = [
        client.post("/api/chat", **question(analysis, f"1.1.1.{i}, 9.9.9.9")).status_code
        for i in range(4)
    ]
    assert codes[-1] == 429


def test_endpoints_share_the_client_budget(client: TestClient, analysis: AnalysisResult) -> None:
    use_llm(FakeLLM([]))
    headers = {"X-Forwarded-For": "9.9.9.9"}
    body = analysis.model_dump()
    assert client.post("/api/insights", json=body, headers=headers).status_code == 200
    assert (
        client.post("/api/mapping/suggest", json={"headers": ["a"]}, headers=headers).status_code
        != 429
    )
    assert client.post("/api/chat", **question(analysis)).status_code == 200
    assert client.post("/api/insights", json=body, headers=headers).status_code == 429


def test_daily_client_cap(
    client: TestClient, analysis: AnalysisResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ai_requests_per_minute", 100)
    monkeypatch.setattr(settings, "ai_requests_per_day", 2)
    use_llm(FakeLLM([]))
    codes = [client.post("/api/chat", **question(analysis)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert "Daily" in client.post("/api/chat", **question(analysis)).json()["detail"]


def test_no_limit_when_ai_is_switched_off(
    analysis: AnalysisResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "ai_requests_per_minute", 1)
    c = TestClient(app)
    use_llm(None)
    try:
        codes = [c.post("/api/insights", json=analysis.model_dump()).status_code for _ in range(5)]
    finally:
        app.dependency_overrides.clear()
    assert codes == [200] * 5


def test_non_ai_endpoints_are_not_limited(client: TestClient) -> None:
    assert all(client.get("/health").status_code == 200 for _ in range(10))


def test_rate_limit_events_are_logged_without_addresses(
    client: TestClient, analysis: AnalysisResult, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    use_llm(FakeLLM([]))
    with caplog.at_level(logging.INFO, logger="app"):
        for _ in range(4):
            client.post("/api/chat", **question(analysis, "9.9.9.9"))
    events = [r for r in caplog.records if r.getMessage() == "rate_limited"]
    assert len(events) == 1 and events[0].fields == {"scope": "minute"}  # type: ignore[attr-defined]
    assert "9.9.9.9" not in "\n".join(
        r.getMessage() + str(getattr(r, "fields", "")) for r in caplog.records
    )


# --- global model-call budget -----------------------------------------------------------------


def test_global_budget_stops_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_core.messages import AIMessage

    from .test_llm import StubChat, gemini  # noqa: PLC0415

    monkeypatch.setattr(settings, "ai_model_calls_per_day", 2)
    llm = gemini(StubChat(AIMessage(content="ok")))
    llm.invoke([Message("user", "a")])
    llm.invoke([Message("user", "b")])
    with pytest.raises(LLMRateLimitError, match="daily AI budget"):
        llm.invoke([Message("user", "c")])


def test_exhausted_global_budget_gives_429_for_chat_and_templates_for_insights(
    client: TestClient, analysis: AnalysisResult
) -> None:
    def exhausted(messages: Any, tools: Any) -> Any:
        raise LLMRateLimitError("The daily AI budget is used up; try again tomorrow.")

    use_llm(FakeLLM([exhausted, exhausted]))
    r = client.post("/api/chat", json=chat_body(analysis, None, ("user", "How risky?")))
    assert r.status_code == 429 and r.json()["error"] == "ai_rate_limited"
    body = client.post("/api/insights", json=analysis.model_dump()).json()
    assert body["source"] == "template"


def test_fake_llm_is_not_charged() -> None:
    llm = FakeLLM([fake_tool_call("get_summary")])
    llm.invoke([Message("user", "x")])
    assert ratelimit.charge_model_call() is None  # budget untouched by the fake


# --- request size caps ------------------------------------------------------------------------


def test_oversized_fake_analysis_is_rejected(client: TestClient, analysis: AnalysisResult) -> None:
    use_llm(FakeLLM([]))
    body = json.loads(analysis.model_dump_json())
    body["weights"] = body["weights"][:1] * 501
    r = client.post("/api/insights", json=body)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    body = json.loads(analysis.model_dump_json())
    body["drawdown_series"] = body["drawdown_series"][:1] * 3001
    assert client.post("/api/insights", json=body).status_code == 422
    assert template_insights(analysis)  # the real analysis is still within the caps


def test_browsers_can_read_retry_after(client: TestClient) -> None:
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    exposed = r.headers["access-control-expose-headers"]
    assert "Retry-After" in exposed and "X-Request-ID" in exposed
