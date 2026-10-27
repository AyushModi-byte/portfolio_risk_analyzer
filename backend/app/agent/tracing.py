"""Optional Langfuse tracing. Off unless both LANGFUSE_* keys are set; nothing depends on it.

The `langfuse` package is not in requirements.txt. If the keys are set but the package is missing
or fails to start, tracing stays off and one warning is logged. Traces include prompts and
answers, so only enable it where sending that text to your Langfuse project is acceptable.
"""

import logging
from functools import lru_cache
from typing import Any

from app.config import settings
from app.observability import log_event


def tracing_enabled() -> bool:
    return bool(settings.langfuse_public_key.strip() and settings.langfuse_secret_key.strip())


@lru_cache(maxsize=1)
def _handler_factory() -> Any | None:
    """A zero-argument callable returning a fresh callback handler, or None if unavailable."""
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        public_key = settings.langfuse_public_key.strip()
        Langfuse(
            public_key=public_key,
            secret_key=settings.langfuse_secret_key.strip(),
            host=settings.langfuse_host.strip() or None,
            release=settings.git_sha,
        )
        return lambda: CallbackHandler(public_key=public_key)
    except Exception as exc:  # missing package, bad keys, anything: tracing must never break AI
        log_event("tracing_unavailable", level=logging.WARNING, error_type=type(exc).__name__)
        return None


def trace_config(name: str, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """LangGraph run config for one flow; carries the Langfuse handler only when tracing is on."""
    config: dict[str, Any] = dict(base or {})
    if not tracing_enabled():
        return config
    factory = _handler_factory()
    if factory is None:
        return config
    try:
        config["callbacks"] = [factory()]
        config["run_name"] = name
    except Exception as exc:
        log_event("tracing_unavailable", level=logging.WARNING, error_type=type(exc).__name__)
    return config
