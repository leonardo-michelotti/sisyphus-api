import httpx
import pytest
import respx
from cachetools import TTLCache

from sisyphus.clients.wikidata import WikidataClient
from sisyphus.clients.wikiquote import WikiquoteClient
from sisyphus.config import settings
from sisyphus.errors import UpstreamError, UpstreamTimeout


def cache() -> TTLCache[str, object]:
    return TTLCache(maxsize=10, ttl=60)


@pytest.mark.asyncio
@respx.mock
async def test_wikiquote_rejects_invalid_json() -> None:
    respx.get(settings.wikiquote_api).mock(
        return_value=httpx.Response(200, text="<html>temporariamente indisponível</html>")
    )
    async with httpx.AsyncClient() as http:
        client = WikiquoteClient(http, cache())
        with pytest.raises(UpstreamError, match="resposta inválida"):
            await client.search("Camus")


@pytest.mark.asyncio
@respx.mock
async def test_wikiquote_rejects_incomplete_quote_payload() -> None:
    respx.get(settings.wikiquote_api).mock(return_value=httpx.Response(200, json={"parse": {}}))
    async with httpx.AsyncClient() as http:
        client = WikiquoteClient(http, cache())
        with pytest.raises(UpstreamError, match="página de frases inválida"):
            await client.get_quotes("Albert Camus")


@pytest.mark.asyncio
@respx.mock
async def test_wikidata_rejects_invalid_json() -> None:
    respx.get(settings.wikidata_api).mock(return_value=httpx.Response(200, text="not-json"))
    async with httpx.AsyncClient() as http:
        client = WikidataClient(http, cache())
        with pytest.raises(UpstreamError, match="resposta inválida"):
            await client.get_profile("Q34670", "Albert Camus")


@pytest.mark.asyncio
@respx.mock
async def test_upstream_timeout_becomes_domain_error() -> None:
    respx.get(settings.wikiquote_api).mock(side_effect=httpx.ReadTimeout("timeout"))
    async with httpx.AsyncClient() as http:
        client = WikiquoteClient(http, cache())
        with pytest.raises(UpstreamTimeout):
            await client.search("Camus")


@pytest.mark.asyncio
@respx.mock
async def test_wikidata_builds_direct_influence_graph() -> None:
    route = respx.get(settings.wikidata_api)
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "entities": {
                    "Q34670": {
                        "claims": {
                            "P737": [
                                {
                                    "rank": "normal",
                                    "mainsnak": {
                                        "datavalue": {
                                            "type": "wikibase-entityid",
                                            "value": {"id": "Q408"},
                                        }
                                    },
                                }
                            ]
                        }
                    }
                }
            },
        ),
        httpx.Response(
            200,
            json={"entities": {"Q408": {"labels": {"pt": {"value": "Sartre"}}}}},
        ),
    ]
    async with httpx.AsyncClient() as http:
        client = WikidataClient(http, cache())
        graph = await client.get_influences("Q34670", "Albert Camus")

    assert graph.pensador.nome == "Albert Camus"
    assert graph.influenciado_por[0].qid == "Q408"
    assert graph.influenciado_por[0].nome == "Sartre"
    assert graph.fonte.licenca == "CC0 1.0"
