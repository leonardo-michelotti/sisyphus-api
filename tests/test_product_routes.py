from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sisyphus.caching import ETagMiddleware
from sisyphus.deps import get_service
from sisyphus.errors import register_error_handlers
from sisyphus.middleware import SecurityHeadersMiddleware
from sisyphus.routers import quotes, web
from sisyphus.schemas import (
    Attribution,
    InfluenceGraph,
    InfluenceNode,
    Quote,
    QuoteCategory,
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


def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(ETagMiddleware, max_age=3600)
    app.add_middleware(SecurityHeadersMiddleware)
    register_error_handlers(app)
    app.include_router(quotes.router)
    app.include_router(web.router)
    app.dependency_overrides[get_service] = lambda: cast(ThinkerService, FakeService())
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
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert "etag" in response.headers


def test_random_quote_is_never_cached() -> None:
    response = client().get("/v1/quotes/random", params={"thinker": "Albert Camus"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers


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
