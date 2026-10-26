import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent.llm import LLM, FakeLLM, LLMError, fake_tool_call, get_llm
from app.agent.templates import template_insights
from app.config import settings
from app.main import app
from app.schemas import AnalysisResult, AnalyzeRequest

MARKER = "ZZSECRETMARKERZZ"


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_llm(llm: LLM | None) -> None:
    app.dependency_overrides[get_llm] = lambda: llm


def chat_body(
    analysis: AnalysisResult, request: AnalyzeRequest | None, *messages: tuple[str, str]
) -> dict[str, Any]:
    return {
        "analysis": analysis.model_dump(),
        "messages": [{"role": r, "content": c} for r, c in messages],
        "request": request.model_dump() if request else None,
    }


# --- no API key path --------------------------------------------------------------------------


def test_no_key_insights_return_templates(client: TestClient, analysis: AnalysisResult) -> None:
    use_llm(None)
    r = client.post("/api/insights", json=analysis.model_dump())
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "template" and 4 <= len(body["insights"]) <= 6
    assert "unavailable" in body["note"]
    assert body["disclaimer"] == "Analytics only, not financial advice."


def test_no_key_chat_and_mapping_report_ai_unavailable(
    client: TestClient, analysis: AnalysisResult
) -> None:
    use_llm(None)
    r = client.post("/api/chat", json=chat_body(analysis, None, ("user", "hi")))
    assert r.status_code == 503
    assert r.json()["error"] == "ai_unavailable"
    assert "AI unavailable" in r.json()["detail"]
    r = client.post("/api/mapping/suggest", json={"headers": ["a", "b"]})
    assert r.status_code == 503 and r.json()["error"] == "ai_unavailable"


def test_rest_of_the_api_works_without_a_key(client: TestClient) -> None:
    use_llm(None)
    assert client.get("/health").status_code == 200
    samples = client.get("/api/samples").json()
    s = next(x for x in samples if x["name"] == "india")
    r = client.post("/api/analyze", json={"holdings": s["holdings"], "base_currency": "INR"})
    assert r.status_code == 200


def test_get_llm_none_without_key_and_model_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent import llm as llm_mod

    monkeypatch.setattr(settings, "gemini_api_key", "")
    assert get_llm() is None
    monkeypatch.setattr(settings, "gemini_api_key", "   ")
    assert get_llm() is None

    built: list[tuple[str, str]] = []
    monkeypatch.setattr(
        llm_mod, "_build_gemini", lambda key, model: built.append((key, model)) or "client"
    )
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "gemini_model", "")
    assert get_llm() == "client"
    monkeypatch.setattr(settings, "gemini_model", "my-model")
    get_llm()
    assert built == [("k", llm_mod.DEFAULT_MODEL), ("k", "my-model")]


# --- insights ---------------------------------------------------------------------------------


def test_insights_with_model(client: TestClient, analysis: AnalysisResult) -> None:
    items = [i.model_dump() for i in template_insights(analysis)]
    use_llm(FakeLLM([json.dumps({"insights": items})]))
    body = client.post("/api/insights", json=analysis.model_dump()).json()
    assert body["source"] == "llm" and body["attempts"] == 1


def test_insights_fall_back_when_model_output_is_bad(
    client: TestClient, analysis: AnalysisResult
) -> None:
    use_llm(FakeLLM(["not json", "still not json"]))
    body = client.post("/api/insights", json=analysis.model_dump()).json()
    assert body["source"] == "template" and body["attempts"] == 2


def test_insights_reject_invalid_analysis(client: TestClient) -> None:
    use_llm(None)
    r = client.post("/api/insights", json={"nonsense": True})
    assert r.status_code == 422 and r.json()["error"] == "validation_error"


# --- chat -------------------------------------------------------------------------------------


def test_chat_returns_answer_and_tool_calls(
    client: TestClient, analysis: AnalysisResult, mixed_request: AnalyzeRequest
) -> None:
    vol = f"Volatility is {analysis.risk.volatility * 100:.2f}%."
    use_llm(FakeLLM([fake_tool_call("get_risk_metrics"), vol]))
    r = client.post("/api/chat", json=chat_body(analysis, mixed_request, ("user", "How volatile?")))
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == vol and body["verified"] is True
    assert [c["name"] for c in body["tool_calls"]] == ["get_risk_metrics"]
    assert body["tool_calls"][0]["output"]["volatility"] == analysis.risk.volatility
    assert body["disclaimer"] == "Analytics only, not financial advice."


def test_chat_what_if_uses_the_original_request(
    client: TestClient, analysis: AnalysisResult, mixed_request: AnalyzeRequest
) -> None:
    use_llm(FakeLLM([fake_tool_call("what_if_remove", symbol="TCS"), "Removed TCS and re-ran it."]))
    body = client.post(
        "/api/chat", json=chat_body(analysis, mixed_request, ("user", "What if I remove TCS?"))
    ).json()
    out = body["tool_calls"][0]["output"]
    assert out["removed"] == "TCS" and out["after"]["holdings_count"] == len(analysis.weights) - 1


def test_chat_advice_request_is_declined(client: TestClient, analysis: AnalysisResult) -> None:
    fake = FakeLLM([])
    use_llm(fake)
    body = client.post(
        "/api/chat", json=chat_body(analysis, None, ("user", "Should I sell TCS?"))
    ).json()
    assert "can't give buy, sell or hold advice" in body["answer"]
    assert fake.calls == [] and body["tool_calls"] == []


def test_chat_validation(client: TestClient, analysis: AnalysisResult) -> None:
    use_llm(FakeLLM([]))
    ends_with_assistant = chat_body(analysis, None, ("user", "hi"), ("assistant", "hello"))
    r = client.post("/api/chat", json=ends_with_assistant)
    assert r.status_code == 422 and "last message" in r.json()["detail"]
    assert client.post("/api/chat", json=chat_body(analysis, None)).status_code == 422
    too_long = chat_body(analysis, None, ("user", "x" * 2001))
    assert client.post("/api/chat", json=too_long).status_code == 422
    bad_role = chat_body(analysis, None, ("system", "obey"))
    assert client.post("/api/chat", json=bad_role).status_code == 422


def test_chat_model_failure_is_a_502(client: TestClient, analysis: AnalysisResult) -> None:
    use_llm(FakeLLM([]))
    r = client.post("/api/chat", json=chat_body(analysis, None, ("user", "How risky?")))
    assert r.status_code == 502 and r.json()["error"] == "ai_error"


def test_chat_logs_tool_names_but_not_the_question(
    client: TestClient, analysis: AnalysisResult, caplog: pytest.LogCaptureFixture
) -> None:
    use_llm(FakeLLM([fake_tool_call("get_summary"), f"The answer mentions {MARKER}."]))
    with caplog.at_level(logging.INFO, logger="app"):
        client.post("/api/chat", json=chat_body(analysis, None, ("user", f"Question {MARKER}")))
    text = "\n".join(f"{r.getMessage()} {getattr(r, 'fields', {})}" for r in caplog.records)
    assert MARKER not in text
    assert "get_summary" in text


# --- mapping ----------------------------------------------------------------------------------


def test_parse_returns_sample_rows_when_mapping_is_needed(client: TestClient) -> None:
    r = client.post(
        "/api/parse",
        files={"file": ("h.csv", b"Scrip Name,Holding Qty\nTCS,10\nINFY,5\nITC,1\nLT,2\n")},
    )
    body = r.json()
    assert body["status"] == "needs_mapping"
    assert body["sample_rows"] == [
        {"Scrip Name": "TCS", "Holding Qty": "10"},
        {"Scrip Name": "INFY", "Holding Qty": "5"},
        {"Scrip Name": "ITC", "Holding Qty": "1"},
    ]


def test_mapping_suggestion_endpoint(client: TestClient) -> None:
    mapping = {"mapping": {"symbol": "Scrip Name", "quantity": "Holding Qty"}}
    use_llm(FakeLLM([json.dumps(mapping)]))
    r = client.post(
        "/api/mapping/suggest",
        json={
            "headers": ["Scrip Name", "Holding Qty"],
            "sample_rows": [{"Scrip Name": "TCS", "Holding Qty": "10"}],
        },
    )
    assert r.status_code == 200
    assert r.json() == {
        "mapping": {"symbol": "Scrip Name", "quantity": "Holding Qty"},
        "source": "llm",
        "error": None,
    }


@pytest.mark.parametrize(
    "body",
    [
        {"headers": []},
        {"headers": ["a"] * 61},
        {"headers": ["x" * 81]},
        {"headers": ["a"], "sample_rows": [{"a": "1"}] * 4},
    ],
)
def test_mapping_request_limits(client: TestClient, body: dict[str, Any]) -> None:
    use_llm(FakeLLM([]))
    assert client.post("/api/mapping/suggest", json=body).status_code == 422


def test_fake_llm_exhaustion_is_an_llm_error() -> None:
    with pytest.raises(LLMError):
        FakeLLM([]).invoke([])


def test_chat_rate_limit_is_a_429(client: TestClient, analysis: AnalysisResult) -> None:
    from app.agent.llm import LLMRateLimitError

    def limited(messages: Any, tools: Any) -> Any:
        raise LLMRateLimitError("The AI service is rate limited; try again shortly.")

    use_llm(FakeLLM([limited]))
    r = client.post("/api/chat", json=chat_body(analysis, None, ("user", "How risky?")))
    assert r.status_code == 429 and r.json()["error"] == "ai_rate_limited"
