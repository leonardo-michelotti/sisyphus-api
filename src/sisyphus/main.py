"""Ponto de entrada da aplicação FastAPI (ADR-002)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .cache import new_cache
from .caching import ETagMiddleware
from .clients.wikidata import WikidataClient
from .clients.wikiquote import WikiquoteClient
from .config import settings
from .errors import register_error_handlers
from .logging_config import setup_logging
from .middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from .ratelimit import RateLimitMiddleware
from .routers import health, quotes, thinkers, web
from .schemas import ProblemDetail
from .services.thinker_service import ThinkerService

# Respostas de erro documentadas no OpenAPI (problem+json, RFC 9457).
_PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetail, "description": "Pensador não encontrado"},
    429: {"model": ProblemDetail, "description": "Limite de requisições excedido"},
    502: {"model": ProblemDetail, "description": "Fonte upstream indisponível"},
    503: {"model": ProblemDetail, "description": "Base curada indisponível"},
    504: {"model": ProblemDetail, "description": "Fonte upstream expirou"},
}

setup_logging(settings.log_level, settings.log_format)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    http = httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": settings.user_agent},
    )
    cache = new_cache()
    wikiquote = WikiquoteClient(http, cache)
    wikidata = WikidataClient(http, cache)
    app.state.http = http  # usado pela readiness (/health/ready)
    app.state.service = ThinkerService(wikiquote, wikidata)
    try:
        yield
    finally:
        await http.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="sisyphus",
        version=__version__,
        summary="API de consulta a pensadores — frases, obras e biografia sobre fontes abertas.",
        description=(
            "Dado um pensador, retorna um perfil com biografia (Wikidata) e frases "
            "(Wikiquote). Conteúdo Wikimedia — atribuição em cada resposta (CC BY-SA / CC0)."
        ),
        lifespan=lifespan,
        debug=settings.debug,
    )
    # Ordem de execução (externo→interno):
    # CORS → SecurityHeaders → RequestId → RateLimit → ETag → app.
    # add_middleware empilha do interno p/ o externo, então a ordem abaixo é invertida.
    app.add_middleware(ETagMiddleware, max_age=settings.http_cache_max_age)
    app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit, window=settings.rate_window)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "ETag", "RateLimit", "RateLimit-Policy"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(thinkers.router, responses=_PROBLEM_RESPONSES)
    app.include_router(quotes.router, responses=_PROBLEM_RESPONSES)
    app.include_router(web.router)
    return app


app = create_app()
