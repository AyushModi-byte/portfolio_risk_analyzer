from fastapi import APIRouter

from app.schemas import AnalysisResult, AnalyzeRequest
from app.services.pipeline import run_analysis

router = APIRouter(prefix="/api")


@router.post("/analyze", response_model=AnalysisResult)
def analyze(req: AnalyzeRequest) -> AnalysisResult:
    return run_analysis(req)
