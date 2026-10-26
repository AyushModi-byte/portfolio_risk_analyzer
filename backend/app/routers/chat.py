from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api")


@router.post("/insights")
def insights() -> None:
    raise HTTPException(status_code=501, detail="Insights are not implemented yet.")


@router.post("/chat")
def chat() -> None:
    raise HTTPException(status_code=501, detail="Chat is not implemented yet.")
