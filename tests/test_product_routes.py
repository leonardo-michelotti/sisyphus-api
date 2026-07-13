from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sisyphus.caching import ETagMiddleware
from sisyphus.deps import get_daily_quote_repository, get_service
from sisyphus.errors import register_error_handlers
from sisyphus.middleware import SecurityHeadersMiddleware
from sisyphus.repositories.quotes import DailyQuoteRepository, SQLiteQuoteRepository
from sisyphus.routers import quotes, web
from sisyphus.schemas import (
    Attribution,
    CuratedQuoteSelection,
    InfluenceGraph,
    InfluenceNode,
    Quote,
    QuoteCategory,
    SelectionMode,
)
from sisyphus.services.thinker_service import ThinkerService


class FakeService:
    async def get_quotes(self, nome: str) -> list[Quote]:
        return [
            Quote(
                texto="Pensar <com cuidado> é parte do trabalho.",
                autor=nome,
                categoria=QuoteCategory.verificada,
                fonte=Attribution(
                    fonte="Wikiquote",
                    licenca="CC BY-SA 4.0",
                    url="https://example.com/quote",
                ),
            )
        ]

    async def get_influences(self, nome: str) -> InfluenceGraph:
        return InfluenceGraph(
            pensador=InfluenceNode(qid="Q34670", nome=nome, url="https://example.com/camus"),
            influenciado_por=[
                InfluenceNode(qid="Q408", nome="Jean-Paul Sartre", url="https://example.com/sartre")
            ],
            fonte=Attribution(fonte="Wikidata", licenca="CC0 1.0", url="https://example.com/camus"),
        )


class FakeDailyRepository:
    def select(self, **_filters: object) -> CuratedQuoteSelection:
        return CuratedQuoteSelection(
            frase=Quote(
                texto="A liberdade é uma oportunidade de ser melhor.",
                autor="Albert Camus",
                categoria=QuoteCategory.verificada,
                fonte=Attribution(
                    fonte="Wikiquote",
                    licenca="CC BY-SA 4.0",
                    url="https://example.com/quote",
                ),
            ),
            modo=SelectionMode.daily,
            data="2026-07-13",
            dataset_version="0123456789abcdef",
            dataset_schema=2,
        )


def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(ETagMiddleware, max_age=3600)
    app.add_middleware(SecurityHeadersMiddleware)
    register_error_handlers(app)
    app.include_router(quotes.router)
    app.include_router(web.router)
    app.dependency_overrides[get_service] = lambda: cast(ThinkerService, FakeService())
    app.dependency_overrides[get_daily_quote_repository] = lambda: cast(
        DailyQuoteRepository, FakeDailyRepository()
    )
    return TestClient(app)


def test_lists_five_editorial_collections() -> None:
    response = client().get("/v1/collections")

    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 5


def test_home_explains_product_and_integrations() -> None:
    response = client().get("/")

    assert response.status_code == 200
    assert "Três superfícies" in response.text
    assert "Notion" in response.text
    assert "Obsidian" in response.text
    assert "Explorar mapa" in response.text
    assert 'aria-label="Navegação principal"' in response.text


def test_quote_of_the_day_exposes_selection_context() -> None:
    response = client().get("/v1/quote-of-the-day", params={"thinker": "Albert Camus"})

    assert response.status_code == 200
    assert response.json()["modo"] == "daily"
    assert response.json()["frase"]["autor"] == "Albert Camus"
    assert response.json()["dataset_version"] == "0123456789abcdef"
    assert response.json()["dataset_schema"] == 2
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert "etag" in response.headers


def test_daily_quote_missing_dataset_uses_problem_details(tmp_path: Path) -> None:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(quotes.router)
    app.dependency_overrides[get_daily_quote_repository] = lambda: SQLiteQuoteRepository(
        tmp_path / "missing.db"
    )

    response = TestClient(app).get("/v1/quote-of-the-day")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "/problems/dataset-unavailable"


def test_random_quote_is_never_cached() -> None:
    response = client().get("/v1/quotes/random", params={"thinker": "Albert Camus"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    assert "dataset_version" not in response.json()
    assert "dataset_schema" not in response.json()


def test_unknown_collection_uses_problem_details() -> None:
    response = client().get("/v1/collections/nao-existe")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "/problems/collection-not-found"


def test_widget_escapes_quote_and_can_be_embedded() -> None:
    response = client().get("/widget", params={"thinker": "Albert Camus"})

    assert response.status_code == 200
    assert "Pensar &lt;com cuidado&gt;" in response.text
    assert "Pensar <com cuidado>" not in response.text
    assert "X-Frame-Options" not in response.headers
    assert "frame-ancestors *" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_influence_page_explains_provenance_and_renders_nodes() -> None:
    response = client().get("/influences", params={"thinker": "Albert Camus"})

    assert response.status_code == 200
    assert "Jean-Paul Sartre" in response.text
    assert "relações P737" in response.text
    assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
