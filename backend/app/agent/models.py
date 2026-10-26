from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas import DISCLAIMER


class Insight(BaseModel):
    text: str
    metric_keys: list[str]


class InsightsResult(BaseModel):
    insights: list[Insight]
    source: Literal["llm", "template"]
    attempts: int = 0  # model calls made before the result was accepted or the fallback used
    note: str | None = None
    disclaimer: str = DISCLAIMER


class ToolRecord(BaseModel):
    name: str
    args: dict[str, Any]
    output: dict[str, Any]


class ChatResult(BaseModel):
    answer: str
    tool_calls: list[ToolRecord] = Field(default_factory=list)
    verified: bool = True  # every number in the answer was found in the tool outputs
    note: str | None = None
    disclaimer: str = DISCLAIMER


class MappingResult(BaseModel):
    mapping: dict[str, str] | None
    source: Literal["llm", "none"]
    error: str | None = None
