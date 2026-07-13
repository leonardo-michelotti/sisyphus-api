"""Rotas editoriais: coleções, frase aleatória e frase do dia."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from ..catalog import get_collection, list_collections
from ..deps import DailyQuotes, Service
from ..schemas import (
    CuratedQuoteSelection,
    EditorialCollection,
    ListMeta,
    Page,
    QuoteCategory,
    QuoteSelection,
    SelectionMode,
)
from ..services.quote_selection import select_quote

router = APIRouter(prefix="/v1", tags=["frases e coleções"])


@router.get("/collections", summary="Lista as coleções editoriais")
async def collections() -> Page[EditorialCollection]:
    items = list_collections()
    return Page(
        data=items,
        meta=ListMeta(count=len(items), limit=len(items), total=len(items), has_more=False),
    )


@router.get("/collections/{slug}", summary="Detalha uma coleção editorial")
async def collection(slug: str) -> EditorialCollection:
    return get_collection(slug)


async def _selection(
    service: Service,
    mode: SelectionMode,
    thinker: str | None,
    collection_slug: str | None,
    category: QuoteCategory | None,
    max_length: int | None,
) -> QuoteSelection:
    return await select_quote(
        service,
        mode=mode,
        thinker=thinker,
        collection_slug=collection_slug,
        category=category,
        max_length=max_length,
    )


@router.get("/quotes/random", summary="Seleciona uma frase aleatória")
async def random_quote(
    service: Service,
    response: Response,
    thinker: Annotated[str | None, Query(description="Nome de uma personalidade")] = None,
    collection: Annotated[str | None, Query(description="Slug de uma coleção")] = None,
    category: QuoteCategory | None = None,
    max_length: Annotated[int | None, Query(ge=40, le=1000)] = None,
) -> QuoteSelection:
    response.headers["Cache-Control"] = "no-store"
    return await _selection(
        service, SelectionMode.random, thinker, collection, category, max_length
    )


@router.get("/quote-of-the-day", summary="Frase diária determinística em UTC")
def quote_of_the_day(
    repository: DailyQuotes,
    thinker: Annotated[str | None, Query(description="Nome de uma personalidade")] = None,
    collection: Annotated[str | None, Query(description="Slug de uma coleção")] = None,
    category: QuoteCategory | None = None,
    max_length: Annotated[int | None, Query(ge=40, le=1000)] = None,
) -> CuratedQuoteSelection:
    return repository.select(
        thinker=thinker,
        collection_slug=collection,
        category=category,
        max_length=max_length,
    )
