from __future__ import annotations

import json
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore


class RedisCache:
    """Optional Redis cache for hot state / locks."""

    def __init__(self, url: str) -> None:
        if redis is None:
            raise RuntimeError("redis package not installed")
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def set_json(self, key: str, value: Any, ttl_sec: int | None = None) -> None:
        data = json.dumps(value, default=str)
        if ttl_sec:
            self._client.setex(key, ttl_sec, data)
        else:
            self._client.set(key, data)

    def get_json(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
