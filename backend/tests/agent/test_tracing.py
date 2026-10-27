import sys
import types
from typing import Any

import pytest

from app.agent import tracing
from app.agent.graph import suggest_mapping
from app.agent.llm import FakeLLM, fake_json
from app.config import settings


@pytest.fixture(autouse=True)
def clear_factory() -> None:
    tracing._handler_factory.cache_clear()


def test_off_by_default_and_config_passes_through() -> None:
    assert not tracing.tracing_enabled()
    assert tracing.trace_config("x", {"recursion_limit": 40}) == {"recursion_limit": 40}


def test_one_key_is_not_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "langfuse_public_key", "pk")
    assert not tracing.tracing_enabled()
    assert "callbacks" not in tracing.trace_config("x")


def test_missing_package_leaves_tracing_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "langfuse_public_key", "pk")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk")
    monkeypatch.setitem(sys.modules, "langfuse", None)  # makes `import langfuse` fail
    assert tracing.trace_config("x", {"a": 1}) == {"a": 1}


def test_enabled_adds_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            started.append(kwargs)

    class FakeHandler:
        def __init__(self, public_key: str) -> None:
            self.public_key = public_key

    lf = types.ModuleType("langfuse")
    lf.Langfuse = FakeClient  # type: ignore[attr-defined]
    lf_lc = types.ModuleType("langfuse.langchain")
    lf_lc.CallbackHandler = FakeHandler  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", lf)
    monkeypatch.setitem(sys.modules, "langfuse.langchain", lf_lc)
    monkeypatch.setattr(settings, "langfuse_public_key", "pk")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk")
    monkeypatch.setattr(settings, "langfuse_host", "https://example.test")

    config = tracing.trace_config("qa_agent", {"recursion_limit": 40})
    assert config["run_name"] == "qa_agent"
    assert config["recursion_limit"] == 40
    assert isinstance(config["callbacks"][0], FakeHandler)
    assert started[0]["host"] == "https://example.test"


def test_flows_work_with_tracing_requested_but_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "langfuse_public_key", "pk")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk")
    monkeypatch.setitem(sys.modules, "langfuse", None)
    llm = FakeLLM([fake_json({"mapping": {"symbol": "Symbol", "quantity": "Qty"}})])
    result = suggest_mapping(llm, ["Symbol", "Qty"], [{"Symbol": "A", "Qty": "1"}])
    assert result.source == "llm"
