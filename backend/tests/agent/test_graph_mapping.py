import json

import pytest

from app.agent import graph
from app.agent.llm import FakeLLM

HEADERS = ["Scrip Name", "Holding Qty", "Cost", "Notes"]
ROWS = [{"Scrip Name": "TCS", "Holding Qty": "10", "Cost": "3100", "Notes": "x"}]
GOOD = {
    "mapping": {
        "symbol": "Scrip Name",
        "quantity": "Holding Qty",
        "avg_buy_price": "Cost",
        "name": None,
    }
}


def test_valid_mapping_is_returned() -> None:
    llm = FakeLLM([json.dumps(GOOD)])
    result = graph.suggest_mapping(llm, HEADERS, ROWS)
    assert result.source == "llm" and result.error is None
    assert result.mapping == {
        "symbol": "Scrip Name",
        "quantity": "Holding Qty",
        "avg_buy_price": "Cost",
    }


def test_input_is_fenced_as_untrusted() -> None:
    llm = FakeLLM([json.dumps(GOOD)])
    graph.suggest_mapping(llm, HEADERS, ROWS)
    messages, _ = llm.calls[0]
    assert messages[1].content.startswith("<untrusted_data>")
    assert "Scrip Name" in messages[1].content


def test_fenced_reply_is_accepted() -> None:
    llm = FakeLLM(["```json\n" + json.dumps(GOOD) + "\n```"])
    assert graph.suggest_mapping(llm, HEADERS, ROWS).mapping is not None


def test_invented_header_is_retried_once() -> None:
    bad = {"mapping": {"symbol": "Ticker", "quantity": "Holding Qty"}}
    llm = FakeLLM([json.dumps(bad), json.dumps(GOOD)])
    result = graph.suggest_mapping(llm, HEADERS, ROWS)
    assert result.mapping is not None and len(llm.calls) == 2
    assert "exact headers" in llm.calls[1][0][-1].content


def test_two_failures_return_no_mapping() -> None:
    bad = json.dumps({"mapping": {"symbol": "Ticker"}})
    llm = FakeLLM([bad, bad, json.dumps(GOOD)])
    result = graph.suggest_mapping(llm, HEADERS, ROWS)
    assert result.mapping is None and result.source == "none"
    assert result.error and len(llm.calls) == 2


@pytest.mark.parametrize(
    ("payload", "needle"),
    [
        ({"mapping": {"symbol": "Scrip Name"}}, "quantity is required"),
        ({"mapping": {"symbol": "Cost", "quantity": "Cost"}}, "only one field"),
        (
            {"mapping": {"symbol": "Scrip Name", "quantity": "Holding Qty", "weird": "Notes"}},
            "Unknown field",
        ),
        ({"mapping": {"symbol": "Scrip Name", "quantity": 3}}, "exact headers"),
        ({"nope": 1}, "Reply must be JSON"),
    ],
)
def test_validation_errors(payload: dict, needle: str) -> None:  # type: ignore[type-arg]
    mapping, errors = graph.validate_mapping(payload, HEADERS)
    assert mapping is None
    assert any(needle in e for e in errors), errors


def test_llm_failure_returns_no_mapping() -> None:
    result = graph.suggest_mapping(FakeLLM([]), HEADERS, ROWS)
    assert result.mapping is None and result.error == "model call failed"
