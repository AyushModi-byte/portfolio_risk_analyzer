from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agent import graph
from app.agent.llm import LLM, AIUnavailableError, get_llm
from app.agent.models import ChatResult, InsightsResult, MappingResult
from app.agent.tools import ToolContext
from app.observability import log_event
from app.ratelimit import ai_guard
from app.schemas import AnalysisResult, AnalyzeRequest
from app.services.pipeline import PipelineError

router = APIRouter(prefix="/api")
MAX_MESSAGE_CHARS = 2000

LLMDep = Annotated[LLM | None, Depends(get_llm)]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    analysis: AnalysisResult
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    # The request that produced `analysis`; only what_if_remove needs it.
    request: AnalyzeRequest | None = None


class MappingRequest(BaseModel):
    headers: list[Annotated[str, Field(max_length=80)]] = Field(min_length=1, max_length=60)
    sample_rows: list[dict[str, Annotated[str, Field(max_length=80)]]] = Field(
        default_factory=list, max_length=3
    )


@router.post("/insights", response_model=InsightsResult, dependencies=[Depends(ai_guard)])
def insights(analysis: AnalysisResult, llm: LLMDep) -> InsightsResult:
    """Validated insights. Without a model key this returns template insights."""
    result = graph.write_insights(analysis, llm)
    log_event("insights", source=result.source, attempts=result.attempts)
    return result


@router.post("/chat", response_model=ChatResult, dependencies=[Depends(ai_guard)])
def chat(req: ChatRequest, llm: LLMDep) -> ChatResult:
    if llm is None:
        raise AIUnavailableError("AI unavailable: no GEMINI_API_KEY is configured.")
    if req.messages[-1].role != "user":
        raise PipelineError("The last message must come from the user.")
    ctx = ToolContext(analysis=req.analysis, request=req.request)
    result = graph.answer_question(llm, ctx, [(m.role, m.content) for m in req.messages])
    log_event(
        "chat",
        tools=[t.name for t in result.tool_calls],
        verified=result.verified,
        note=result.note,
    )
    return result


@router.post("/mapping/suggest", response_model=MappingResult, dependencies=[Depends(ai_guard)])
def suggest_mapping(req: MappingRequest, llm: LLMDep) -> MappingResult:
    """Ask the model to map unrecognised columns. The user confirms the result in the UI."""
    if llm is None:
        raise AIUnavailableError("AI unavailable: no GEMINI_API_KEY is configured.")
    result = graph.suggest_mapping(llm, req.headers, req.sample_rows)
    log_event("mapping_suggestion", source=result.source)
    return result
