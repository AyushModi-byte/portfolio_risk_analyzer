import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser

from app.config import settings
from app.errors import error_response, install_error_handlers
from app.observability import log_event, request_id_var, setup_logging
from app.routers import analyze, chat, health, parse

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
BODY_OVERHEAD_BYTES = 64 * 1024  # multipart framing on top of the file itself

CallNext = Callable[[Request], Awaitable[Response]]


async def _guarded(request: Request, call_next: CallNext) -> Response:
    """Reject oversized bodies before they are read, and turn unexpected errors into JSON."""
    if request.method == "POST":
        length = request.headers.get("content-length")
        if length is None and request.url.path == "/api/parse":
            return error_response(411, "Content-Length header is required for uploads.")
        limit = settings.max_upload_mb * 1024 * 1024 + BODY_OVERHEAD_BYTES
        if length is not None and length.isdigit() and int(length) > limit:
            return error_response(413, f"Request is larger than {settings.max_upload_mb} MB.")
    try:
        return await call_next(request)
    except Exception as exc:
        # Type only: messages and tracebacks could contain uploaded data.
        log_event("unhandled_error", level=logging.ERROR, error_type=type(exc).__name__)
        return error_response(500, "Internal server error.", "internal_error")


def create_app() -> FastAPI:
    setup_logging()
    # Keep uploads in memory: Starlette would otherwise spool files over 1 MB to a temp file.
    MultiPartParser.spool_max_size = (settings.max_upload_mb + 1) * 1024 * 1024

    app = FastAPI(title="Portfolio Risk Analyzer", version=health.VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next: CallNext) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await _guarded(request, call_next)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            log_event(
                "request",
                method=request.method,
                route=getattr(request.scope.get("route"), "path", "unmatched"),
                path=request.url.path,
                status=status,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
            )
            request_id_var.reset(token)

    app.include_router(health.router)
    app.include_router(parse.router)
    app.include_router(analyze.router)
    app.include_router(chat.router)
    return app


app = create_app()
