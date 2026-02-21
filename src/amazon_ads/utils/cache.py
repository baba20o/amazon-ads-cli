"""In-memory TTL cache for Amazon Ads API responses."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ResponseCache:
    """In-memory TTL cache for API read operations.

    Cache keys are derived from (method, path, region, serialized_body).
    Write operations (PUT, DELETE, non-list POST) invalidate region-scoped entries.
    """

    def __init__(self, ttl: int = 300, enabled: bool = True) -> None:
        self._ttl = ttl
        self._enabled = enabled
        self._store: dict[str, tuple[float, Any]] = {}
        self._region_keys: dict[str, set[str]] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def is_cacheable_request(method: str, path: str) -> bool:
        """Determine if a request should be cached.

        Cacheable: GET requests, POST to /list endpoints.
        Not cacheable: POST creates, POST /delete, PUT, DELETE.
        """
        method = method.upper()
        if method == "GET":
            return True
        if method == "POST" and path.rstrip("/").endswith("/list"):
            return True
        return False

    @staticmethod
    def is_write_request(method: str, path: str) -> bool:
        """Determine if a request should invalidate cache.

        Writes: PUT, DELETE, POST without /list suffix.
        """
        method = method.upper()
        if method in ("PUT", "DELETE"):
            return True
        if method == "POST" and not path.rstrip("/").endswith("/list"):
            return True
        return False

    def make_key(self, method: str, path: str, region: str, body: Any = None) -> str:
        """Generate a deterministic cache key."""
        body_str = json.dumps(body, sort_keys=True, default=str) if body else ""
        raw = f"{method.upper()}|{path}|{region.upper()}|{body_str}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Retrieve a cached response if it exists and has not expired."""
        if not self._enabled:
            return None

        entry = self._store.get(key)
        if entry is None:
            return None

        timestamp, data = entry
        if time.time() - timestamp > self._ttl:
            self._remove_key(key)
            return None

        return data

    def put(self, key: str, data: Any, region: str) -> None:
        """Store a response in the cache."""
        if not self._enabled:
            return

        self._store[key] = (time.time(), data)
        region = region.upper()
        if region not in self._region_keys:
            self._region_keys[region] = set()
        self._region_keys[region].add(key)

    def invalidate_region(self, region: str) -> int:
        """Invalidate all cached entries for a specific region."""
        region = region.upper()
        keys = self._region_keys.pop(region, set())
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    def invalidate_all(self) -> int:
        """Clear the entire cache."""
        count = len(self._store)
        self._store.clear()
        self._region_keys.clear()
        return count

    def _remove_key(self, key: str) -> None:
        """Remove a single key from store and region index."""
        self._store.pop(key, None)
        for region_set in self._region_keys.values():
            region_set.discard(key)

    @property
    def size(self) -> int:
        """Number of entries currently in the cache."""
        return len(self._store)
