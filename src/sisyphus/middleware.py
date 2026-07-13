"""Middleware de correlação: um X-Request-ID por requisição (ADR-022).

Reaproveita o header recebido (se o cliente/edge já mandou um) ou gera um novo;
publica-o no ContextVar para os logs e o devolve na resposta.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging_config import request_id_ctx

HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers defensivos sem impedir que `/widget` seja incorporado."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path == "/widget":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'unsafe-inline'; img-src 'self' data:; "
                "base-uri 'none'; form-action 'none'; frame-ancestors *"
            )
        elif request.url.path in {"/", "/influences"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "frame-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
            )
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get(HEADER, "")
        rid = supplied if _VALID_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers[HEADER] = rid
        return response
