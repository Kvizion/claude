"""A tiny thread-safe TTL cache used by a few tools (e.g. system info)."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional


class TTLCache:
    def __init__(self, default_ttl: float = 5.0) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + (ttl or self._default_ttl), value)

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
