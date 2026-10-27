from fastapi import APIRouter

from app.config import settings

router = APIRouter()
VERSION = "0.1.0"


@router.get("/health")
def health() -> dict[str, str | bool]:
    """Liveness plus whether AI features are configured, so the UI can hide them."""
    return {
        "status": "ok",
        "version": VERSION,
        "git_sha": settings.git_sha,
        "ai_available": bool(settings.gemini_api_key.strip()),
    }
