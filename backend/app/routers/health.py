from fastapi import APIRouter

from app.config import settings

router = APIRouter()
VERSION = "0.1.0"


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION, "git_sha": settings.git_sha}
