"""Rotas de pensadores: perfil, frases e busca."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from ..deps import Service
from ..schemas import InfluenceGraph, ListMeta, Page, Quote, SearchHit, ThinkerProfile

router = APIRouter(prefix="/v1", tags=["pensadores"])


@router.get("/search", summary="Busca pensadores por nome")
async def search(
    service: Service,
    q: Annotated[str, Query(min_length=1, description="Nome ou parte do nome")],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> Page[SearchHit]:
    hits = await service.search(q, limit=limit)
    meta = ListMeta(count=len(hits), limit=limit, has_more=len(hits) == limit)
    return Page(data=hits, meta=meta)


@router.get("/thinkers/{nome}", summary="Perfil: biografia + amostra de frases")
async def get_thinker(
    service: Service,
    nome: str,
    frases: Annotated[int, Query(ge=0, le=50, description="Nº de frases na amostra")] = 10,
) -> ThinkerProfile:
    return await service.get_profile(nome, sample=frases)


@router.get("/thinkers/{nome}/quotes", summary="Frases do pensador (paginado)")
async def get_thinker_quotes(
    service: Service,
    nome: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[Quote]:
    quotes = await service.get_quotes(nome)
    window = quotes[offset : offset + limit]
    meta = ListMeta(
        count=len(window),
        limit=limit,
        offset=offset,
        total=len(quotes),
        has_more=offset + limit < len(quotes),
    )
    return Page(data=window, meta=meta)


@router.get(
    "/thinkers/{nome}/influences",
    summary="Grafo direto de influências intelectuais",
)
async def get_thinker_influences(service: Service, nome: str) -> InfluenceGraph:
    return await service.get_influences(nome)
