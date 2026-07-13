from datetime import date
from typing import cast

import pytest

from sisyphus.errors import CollectionNotFound, InvalidSelection, NoQuotesAvailable
from sisyphus.schemas import Attribution, Quote, QuoteCategory, SelectionMode
from sisyphus.services.quote_selection import select_quote
from sisyphus.services.thinker_service import ThinkerService


class FakeService:
    def __init__(self) -> None:
        source = Attribution(fonte="Wikiquote", licenca="CC BY-SA 4.0", url="https://example.com")
        self.quotes = {
            "Albert Camus": [
                Quote(
                    texto="A liberdade é uma oportunidade de ser melhor.",
                    autor="Albert Camus",
                    categoria=QuoteCategory.verificada,
                    fonte=source,
                ),
                Quote(
                    texto="Criar é viver duas vezes.",
                    autor="Albert Camus",
                    categoria=QuoteCategory.obra,
                    obra="O Mito de Sísifo",
                    fonte=source,
                ),
            ]
        }

    async def get_quotes(self, nome: str) -> list[Quote]:
        return self.quotes.get(nome, [])


@pytest.fixture
def service() -> ThinkerService:
    return cast(ThinkerService, FakeService())


@pytest.mark.asyncio
async def test_daily_selection_is_stable(service: ThinkerService) -> None:
    kwargs = {
        "mode": SelectionMode.daily,
        "thinker": "Albert Camus",
        "on_date": date(2026, 7, 12),
    }
    first = await select_quote(service, **kwargs)
    second = await select_quote(service, **kwargs)

    assert first == second
    assert first.data == "2026-07-12"


@pytest.mark.asyncio
async def test_selection_applies_category_and_length(service: ThinkerService) -> None:
    result = await select_quote(
        service,
        mode=SelectionMode.daily,
        thinker="Albert Camus",
        category=QuoteCategory.obra,
        max_length=80,
        on_date=date(2026, 7, 12),
    )

    assert result.frase.categoria is QuoteCategory.obra
    assert len(result.frase.texto) <= 80


@pytest.mark.asyncio
async def test_selection_rejects_unknown_collection(service: ThinkerService) -> None:
    with pytest.raises(CollectionNotFound):
        await select_quote(service, mode=SelectionMode.daily, collection_slug="nao-existe")


@pytest.mark.asyncio
async def test_selection_reports_empty_filters(service: ThinkerService) -> None:
    with pytest.raises(NoQuotesAvailable):
        await select_quote(
            service,
            mode=SelectionMode.daily,
            thinker="Albert Camus",
            max_length=10,
        )


@pytest.mark.asyncio
async def test_thinker_must_belong_to_selected_collection(service: ThinkerService) -> None:
    with pytest.raises(InvalidSelection):
        await select_quote(
            service,
            mode=SelectionMode.daily,
            thinker="Albert Camus",
            collection_slug="ciencia-e-curiosidade",
        )
