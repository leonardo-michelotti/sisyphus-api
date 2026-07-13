"""Erros tipados + handlers problem+json — RFC 9457 (ADR-007).

Distingue 'pensador não encontrado' (404) de 'fonte upstream falhou/expirou'
(502/504), em vez do antigo 200-com-lista-vazia. Cada erro carrega um `type`
(URI do tipo do problema) e o handler injeta o `instance` (path da requisição).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .schemas import ProblemDetail


class SisyphusError(Exception):
    """Base dos erros de domínio. `status` vira o HTTP status; `type` o problem type."""

    status: int = 500
    title: str = "Erro interno"
    type: str = "about:blank"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(detail or self.title)


class ThinkerNotFound(SisyphusError):
    status = 404
    title = "Pensador não encontrado"
    type = "/problems/thinker-not-found"


class CollectionNotFound(SisyphusError):
    status = 404
    title = "Coleção não encontrada"
    type = "/problems/collection-not-found"


class NoQuotesAvailable(SisyphusError):
    status = 404
    title = "Nenhuma frase disponível"
    type = "/problems/no-quotes-available"


class InvalidSelection(SisyphusError):
    status = 422
    title = "Seleção inválida"
    type = "/problems/invalid-selection"


class UpstreamError(SisyphusError):
    status = 502
    title = "Fonte upstream indisponível"
    type = "/problems/upstream-error"


class UpstreamTimeout(SisyphusError):
    status = 504
    title = "Fonte upstream expirou"
    type = "/problems/upstream-timeout"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SisyphusError)
    async def _handle(request: Request, exc: SisyphusError) -> JSONResponse:
        body = ProblemDetail(
            type=exc.type,
            title=exc.title,
            status=exc.status,
            detail=exc.detail,
            instance=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status,
            content=body.model_dump(),
            media_type="application/problem+json",
        )
