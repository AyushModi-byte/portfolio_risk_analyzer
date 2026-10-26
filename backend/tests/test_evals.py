"""The offline agent eval runs in CI with the scripted model."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_agent_eval as ev  # noqa: E402


@pytest.fixture(scope="module")
def questions() -> list[dict]:  # type: ignore[type-arg]
    return ev.load_questions()


def test_question_file_covers_the_required_cases(questions: list[dict]) -> None:  # type: ignore[type-arg]
    assert len(questions) >= 25
    assert len({q["id"] for q in questions}) == len(questions)
    categories = {q["category"] for q in questions}
    assert {
        "holdings",
        "sectors",
        "risk",
        "drawdown",
        "what_if",
        "advice",
        "injection",
    } <= categories
    assert sum(q["category"] == "advice" for q in questions) >= 3


def test_real_mode_skips_fake_only_questions() -> None:
    all_q = ev.load_questions()
    real_q = ev.load_questions(real_llm=True)
    assert 0 < len(all_q) - len(real_q) <= 2
    assert all(not q.get("fake_only") for q in real_q)


def test_fake_llm_eval_meets_targets(
    questions: list[dict], capsys: pytest.CaptureFixture[str]
) -> None:  # type: ignore[type-arg]
    analysis, request = ev.build_context()
    assert ev.INJECTION_SYMBOL in {w.symbol for w in analysis.weights}
    report = ev.run_eval(questions, analysis, request, ev.fake_llm_for)
    ev.print_report(report, "fake LLM", verbose=False)
    out = capsys.readouterr().out
    for metric in ("tool_selection_accuracy", "numeric_accuracy", "numbers_not_in_tool_outputs"):
        assert metric in out
    assert report.tool_selection_accuracy == 1.0
    assert report.numeric_accuracy == 1.0
    assert report.unsupported_numbers == 0
    assert report.advice_violations == 0
    assert report.errors == 0
    # the two scripted misbehaving models (hallucinated number, compliance with injection)
    assert {r.id for r in report.results if not r.verified} == {
        "injection_in_question",
        "hallucinated_number",
    }
    advice = [r for r in report.results if r.category == "advice"]
    assert all(r.tools_called == [] and "advice" in (r.note or "") for r in advice)


def test_main_fake_exit_code_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "results.json"
    assert ev.main(["--fake-llm", "--json", str(out)]) == 0
    assert out.exists() and "top_holding" in out.read_text(encoding="utf-8")
    assert "tool_selection_accuracy : 100.0%" in capsys.readouterr().out


def test_main_real_mode_without_key_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert ev.main([]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


def test_scoring_catches_wrong_tools_and_leaked_numbers() -> None:
    from app.agent.llm import FakeLLM, fake_tool_call

    analysis, request = ev.build_context()
    q = {
        "id": "t",
        "category": "risk",
        "question": "Volatility?",
        "tools": [{"name": "get_risk_metrics"}],
        "numbers": ["risk.volatility"],
    }
    wrong_tool = FakeLLM([fake_tool_call("get_summary"), "Value is high."])
    report = ev.run_eval([q], analysis, request, lambda _: wrong_tool)
    r = report.results[0]
    assert not r.tool_ok and r.numbers_found == 0 and report.tool_selection_accuracy == 0.0
    erroring = ev.run_eval([q], analysis, request, lambda _: FakeLLM([]))
    assert erroring.errors == 1 and not erroring.results[0].tool_ok
