"""Abuse protection for the AI endpoints, which spend the owner's Gemini quota.

Three layers, all in memory (the backend is stateless and single-process on Render):
per-client requests per minute, per-client requests per day, and a global daily budget of model
calls shared by everyone. Limits are read from settings on each check so they can be tuned by
environment variable without code changes.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

from app.config import settings
from app.observability import log_event

MINUTE = 60.0
DAY = 86400.0


class RateLimitedError(Exception):
    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = max(1, retry_after)


class SlidingWindow:
    """Allow at most `limit` events per `window` seconds for each key."""

    def __init__(self, max_keys: int = 10_000, clock: Callable[[], float] = time.monotonic) -> None:
        self._events: dict[str, deque[float]] = {}
        self._max_keys = max_keys
        self._clock = clock
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: float) -> int | None:
        """Record an event. Returns None if allowed, else seconds until the next slot frees up."""
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self._max_keys:
                    self._evict(now, window)
                events = self._events[key] = deque()
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                return int(events[0] + window - now) + 1
            events.append(now)
            return None

    def _evict(self, now: float, window: float) -> None:
        stale = [k for k, e in self._events.items() if not e or e[-1] <= now - window]
        for k in stale or [next(iter(self._events))]:
            del self._events[k]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class DailyBudget:
    """A shared counter that resets every 24 hours after its first use."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._used = 0
        self._reset_at = 0.0
        self._lock = threading.Lock()

    def charge(self, limit: int) -> int | None:
        """Spend one unit. Returns None if allowed, else seconds until the budget resets."""
        now = self._clock()
        with self._lock:
            if now >= self._reset_at:
                self._used, self._reset_at = 0, now + DAY
            if self._used >= limit:
                return int(self._reset_at - now) + 1
            self._used += 1
            return None

    def clear(self) -> None:
        with self._lock:
            self._used, self._reset_at = 0, 0.0


_per_client = SlidingWindow()
_model_calls = DailyBudget()


def reset() -> None:
    _per_client.clear()
    _model_calls.clear()


def client_key(request: Request) -> str:
    """The caller's address. Behind trusted proxies, take the entry the nearest one appended.

    Anything the client put earlier in X-Forwarded-For is ignored, so it cannot dodge the limit
    by inventing addresses. Set TRUSTED_PROXY_HOPS=0 when the app is exposed directly.
    """
    hops = settings.trusted_proxy_hops
    forwarded = request.headers.get("x-forwarded-for", "")
    if hops > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


def ai_guard(request: Request) -> None:
    """FastAPI dependency for endpoints that may call the model."""
    if not settings.gemini_api_key.strip():
        return  # nothing to protect: AI features are off
    key = client_key(request)
    wait = _per_client.hit(f"m:{key}", settings.ai_requests_per_minute, MINUTE)
    if wait is not None:
        log_event("rate_limited", scope="minute")
        raise RateLimitedError("Too many AI requests. Please wait a moment and try again.", wait)
    wait = _per_client.hit(f"d:{key}", settings.ai_requests_per_day, DAY)
    if wait is not None:
        log_event("rate_limited", scope="day")
        raise RateLimitedError("Daily AI request limit reached. Please try again tomorrow.", wait)


def charge_model_call() -> int | None:
    """Spend one unit of the global daily model-call budget. None if allowed."""
    return _model_calls.charge(settings.ai_model_calls_per_day)
