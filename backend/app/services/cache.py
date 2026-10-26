"""Small thread-safe in-memory TTL cache."""

import threading
import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float, maxsize: int = 256) -> None:
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._data: dict[object, tuple[float, T]] = {}
        self._lock = threading.Lock()

    def get(self, key: object) -> T | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < time.monotonic():
                del self._data[key]
                return None
            return value

    def set(self, key: object, value: T) -> None:
        with self._lock:
            if len(self._data) >= self.maxsize and key not in self._data:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (time.monotonic() + self.ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
