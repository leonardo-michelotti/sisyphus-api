"""Rate limiting em memória + headers padrão IETF (ADR-014).

Emite `RateLimit-Policy` e `RateLimit` conforme
draft-ietf-httpapi-ratelimit-headers-11 — o cliente vê a quota e pode se
auto-regular, em vez de só apanhar 429. Janela fixa por IP; suficiente para uma
única réplica (mesma premissa do cache em memória, ADR-005).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from .schemas import ProblemDetail

_POLICY = "default"
_PRUNE_AT = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limit: int, window: int) -> None:
        super().__init__(app)
        self._limit = limit
        self._window = window
        self._hits: dict[str, tuple[float, int]] = {}

    def _client_key(self, request: Request) -> str:
        # Atrás de proxy/edge (Railway), o IP real vem no X-Forwarded-For.
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        now = time.monotonic()
        key = self._client_key(request)
        window_start, count = self._hits.get(key, (now, 0))
        if now - window_start >= self._window:
            window_start, count = now, 0
        count += 1
        self._hits[key] = (window_start, count)
        self._maybe_prune(now)

        remaining = max(0, self._limit - count)
        reset = max(0, int(self._window - (now - window_start)))
        policy = f'"{_POLICY}";q={self._limit};w={self._window}'
        limit_status = f'"{_POLICY}";r={remaining};t={reset}'

        if count > self._limit:
            body = ProblemDetail(
                type="/problems/rate-limited",
                title="Too Many Requests",
                status=429,
                detail="Limite de requisições excedido. Tente novamente mais tarde.",
                instance=request.url.path,
            )
            response: Response = JSONResponse(
                status_code=429,
                content=body.model_dump(),
                media_type="application/problem+json",
            )
            response.headers["Retry-After"] = str(reset)
        else:
            response = await call_next(request)

        response.headers["RateLimit-Policy"] = policy
        response.headers["RateLimit"] = limit_status
        return response

    def _maybe_prune(self, now: float) -> None:
        """Descarta janelas expiradas quando o mapa cresce (limita memória)."""
        if len(self._hits) < _PRUNE_AT:
            return
        expired = [k for k, (ws, _) in self._hits.items() if now - ws >= self._window]
        for k in expired:
            del self._hits[k]
