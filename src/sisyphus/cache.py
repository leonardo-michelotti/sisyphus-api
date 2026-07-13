"""Cache TTL em memória (ADR-005). Redis fica como evolução se houver réplicas."""

from __future__ import annotations

from typing import Any

from cachetools import TTLCache

from .config import settings


def new_cache() -> TTLCache[str, Any]:
    return TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
