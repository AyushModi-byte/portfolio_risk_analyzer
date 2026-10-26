from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.parsers import ParseError
from app.services.pipeline import PipelineError

# Pinned because http.HTTPStatus phrases differ between Python versions.
ERROR_SLUGS = {413: "payload_too_large", 415: "unsupported_media_type", 422: "unprocessable"}


def error_response(status_code: int, detail: str, error: str | None = None) -> JSONResponse:
    if error is None and status_code in ERROR_SLUGS:
        error = ERROR_SLUGS[status_code]
    if error is None:
        try:
            error = HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
        except ValueError:
            error = "error"
    return JSONResponse(status_code=status_code, content={"error": error, "detail": detail})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only location and message: pydantic's `input` could echo uploaded content.
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return error_response(422, detail, "validation_error")

    @app.exception_handler(ParseError)
    async def parse_error(_: Request, exc: ParseError) -> JSONResponse:
        return error_response(exc.status_code, str(exc))

    @app.exception_handler(PipelineError)
    async def pipeline_error(_: Request, exc: PipelineError) -> JSONResponse:
        return error_response(exc.status_code, str(exc))
