"""ETag + Cache-Control com conditional GET nas rotas /v1 (ADR-021).

O conteúdo (frases/bio) é ~imutável, então vale caching HTTP: calcula um ETag
do corpo, responde 304 quando o cliente manda `If-None-Match` casado e evita
retransmitir o payload.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class ETagMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_age: int) -> None:
        super().__init__(app)
        self._max_age = max_age

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if (
            request.method != "GET"
            or response.status_code != 200
            or not request.url.path.startswith("/v1")
            or "no-store" in response.headers.get("cache-control", "").lower()
        ):
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
        etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["ETag"] = etag
        headers["Cache-Control"] = f"public, max-age={self._max_age}"

        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(
            content=body,
            status_code=200,
            headers=headers,
            media_type=response.media_type,
        )
