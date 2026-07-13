"""Seleção de frases para os modos aleatório e frase do dia."""

from __future__ import annotations

import hashlib
import random
import secrets
from datetime import date, datetime, timezone

from ..catalog import ALL_THINKERS, get_collection
from ..errors import InvalidSelection, NoQuotesAvailable, SisyphusError
from ..schemas import Quote, QuoteCategory, QuoteSelection, SelectionMode
from .thinker_service import ThinkerService


def _seed(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], byteorder="big")


def _filter_quotes(
    quotes: list[Quote], category: QuoteCategory | None, max_length: int | None
) -> list[Quote]:
    return [
        quote
        for quote in quotes
        if (category is None or quote.categoria == category)
        and (max_length is None or len(quote.texto) <= max_length)
    ]


async def select_quote(
    service: ThinkerService,
    *,
    mode: SelectionMode,
    thinker: str | None = None,
    collection_slug: str | None = None,
    category: QuoteCategory | None = None,
    max_length: int | None = None,
    on_date: date | None = None,
) -> QuoteSelection:
    collection = get_collection(collection_slug) if collection_slug else None
    if thinker and collection and thinker not in collection.pensadores:
        raise InvalidSelection(f"{thinker!r} não pertence à coleção {collection.titulo!r}")
    candidates = (
        [thinker] if thinker else list(collection.pensadores if collection else ALL_THINKERS)
    )

    selected_date: date | None = None
    if mode is SelectionMode.daily:
        selected_date = on_date or datetime.now(timezone.utc).date()
        key = "|".join(
            [
                selected_date.isoformat(),
                thinker or "",
                collection_slug or "",
                category.value if category else "",
                str(max_length or ""),
            ]
        )
        rng = random.Random(_seed(key))
    else:
        rng = random.Random(secrets.randbits(64))

    rng.shuffle(candidates)
    last_error: SisyphusError | None = None
    for candidate in candidates:
        try:
            quotes = _filter_quotes(await service.get_quotes(candidate), category, max_length)
        except SisyphusError as exc:
            if thinker:
                raise
            last_error = exc
            continue
        if quotes:
            return QuoteSelection(
                frase=rng.choice(quotes),
                modo=mode,
                data=selected_date.isoformat() if selected_date else None,
                colecao=collection,
            )

    detail = "Nenhuma frase corresponde aos filtros informados"
    if last_error:
        detail += f"; última fonte consultada: {last_error}"
    raise NoQuotesAvailable(detail)
