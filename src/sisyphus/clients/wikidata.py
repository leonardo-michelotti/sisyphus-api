"""Client do Wikidata via REST `wbgetentities` (ADR-017).

Escolhido em vez do SPARQL por ser CDN-cacheado e estável (o SPARQL público deu
429 por outage no teste). Custo: duas idas à rede — (1) claims da entidade,
(2) resolução em batch dos labels das entidades referenciadas.
"""

from __future__ import annotations

from typing import Any

import httpx
from cachetools import TTLCache

from ..config import settings
from ..dates import parse_wikidata_time
from ..errors import UpstreamError, UpstreamTimeout
from ..schemas import Attribution, InfluenceGraph, InfluenceNode, PartialDate, Thinker, Work

# Propriedades do perfil (fixadas em PILARES_TECNICOS.md).
P_BIRTH_DATE = "P569"
P_DEATH_DATE = "P570"
P_BIRTH_PLACE = "P19"
P_CITIZENSHIP = "P27"
P_OCCUPATION = "P106"
P_MOVEMENT = "P135"
P_EDUCATION = "P69"
P_NOTABLE_WORKS = "P800"
P_INFLUENCED_BY = "P737"

_ENTITY_PROPS = [P_BIRTH_PLACE, P_CITIZENSHIP, P_OCCUPATION, P_MOVEMENT, P_EDUCATION]


def _best_claim(claims: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Statement de maior confiança: rank `preferred` primeiro, ignora `deprecated`."""
    usable = [c for c in claims if c.get("rank") != "deprecated"]
    if not usable:
        return None
    for c in usable:
        if c.get("rank") == "preferred":
            return c
    return usable[0]


def _datavalue(claim: dict[str, Any]) -> dict[str, Any] | None:
    dv = claim.get("mainsnak", {}).get("datavalue")
    return dv if isinstance(dv, dict) else None


def _entity_ids(claims: list[dict[str, Any]]) -> list[str]:
    ids = []
    for c in claims:
        if c.get("rank") == "deprecated":
            continue
        dv = _datavalue(c)
        if dv and dv.get("type") == "wikibase-entityid":
            ids.append(dv["value"]["id"])
    return ids


def _date(claims: list[dict[str, Any]]) -> PartialDate | None:
    best = _best_claim(claims)
    if not best:
        return None
    dv = _datavalue(best)
    if not dv or dv.get("type") != "time":
        return None
    return parse_wikidata_time(dv["value"]["time"], dv["value"]["precision"])


def collect_referenced_ids(claims: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Todos os QIDs referenciados nas props que precisam de label."""
    refs: set[str] = set()
    for pid in (*_ENTITY_PROPS, P_NOTABLE_WORKS):
        refs.update(_entity_ids(claims.get(pid, [])))
    return refs


def build_thinker(
    qid: str,
    nome: str,
    entity: dict[str, Any],
    labels: dict[str, str],
) -> Thinker:
    """Monta o `Thinker` a partir da entidade e dos labels resolvidos (função pura).

    Labels ausentes (sem pt/en) são omitidos — nunca vaza QID cru para o cliente.
    """
    claims: dict[str, list[dict[str, Any]]] = entity.get("claims", {})
    descriptions = entity.get("descriptions", {})
    descricao = (descriptions.get("pt") or descriptions.get("en") or {}).get("value")

    def labeled(pid: str) -> list[str]:
        return [labels[q] for q in _entity_ids(claims.get(pid, [])) if q in labels]

    birth_place = next(iter(labeled(P_BIRTH_PLACE)), None)
    obras = [
        Work(titulo=labels[q], qid=q)
        for q in _entity_ids(claims.get(P_NOTABLE_WORKS, []))
        if q in labels
    ]

    return Thinker(
        qid=qid,
        nome=nome,
        descricao=descricao,
        nascimento=_date(claims.get(P_BIRTH_DATE, [])),
        morte=_date(claims.get(P_DEATH_DATE, [])),
        local_nascimento=birth_place,
        nacionalidade=labeled(P_CITIZENSHIP),
        ocupacoes=labeled(P_OCCUPATION),
        correntes=labeled(P_MOVEMENT),
        formacao=labeled(P_EDUCATION),
        obras=obras,
        fontes=[
            Attribution(
                fonte="Wikidata", licenca="CC0 1.0", url=f"https://www.wikidata.org/wiki/{qid}"
            ),
        ],
    )


class WikidataClient:
    def __init__(self, http: httpx.AsyncClient, cache: TTLCache[str, Any]) -> None:
        self._http = http
        self._cache = cache

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "format": "json", "formatversion": "2"}
        try:
            resp = await self._http.get(settings.wikidata_api, params=params)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise UpstreamTimeout("Wikidata não respondeu a tempo") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Falha ao consultar o Wikidata: {exc}") from exc
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("Wikidata devolveu uma resposta inválida") from exc
        if not isinstance(data, dict):
            raise UpstreamError("Wikidata devolveu um payload inesperado")
        return data

    async def _labels(self, ids: list[str]) -> dict[str, str]:
        """Resolve labels (pt->en) em batches de 50."""
        out: dict[str, str] = {}
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            data = await self._get(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "labels",
                    "languages": "pt|en",
                }
            )
            for q, ent in data.get("entities", {}).items():
                lbl = ent.get("labels", {})
                value = (lbl.get("pt") or lbl.get("en") or {}).get("value")
                if value:
                    out[q] = value
        return out

    async def get_profile(self, qid: str, nome: str) -> Thinker:
        key = f"profile:{qid}"
        if key in self._cache:
            return self._cache[key]  # type: ignore[no-any-return]

        data = await self._get(
            {
                "action": "wbgetentities",
                "ids": qid,
                "props": "claims|descriptions|labels",
                "languages": "pt|en",
            }
        )
        entity = data.get("entities", {}).get(qid)
        if not entity or "missing" in entity:
            raise UpstreamError(f"Entidade {qid} não encontrada no Wikidata")

        refs = sorted(collect_referenced_ids(entity.get("claims", {})))
        labels = await self._labels(refs)
        thinker = build_thinker(qid, nome, entity, labels)
        self._cache[key] = thinker
        return thinker

    async def get_influences(self, qid: str, nome: str) -> InfluenceGraph:
        """Obtém as influências intelectuais diretas declaradas em P737."""
        key = f"influences:{qid}"
        if key in self._cache:
            return self._cache[key]  # type: ignore[no-any-return]

        data = await self._get(
            {"action": "wbgetentities", "ids": qid, "props": "claims", "languages": "pt|en"}
        )
        entity = data.get("entities", {}).get(qid)
        if not entity or "missing" in entity:
            raise UpstreamError(f"Entidade {qid} não encontrada no Wikidata")

        influence_ids = list(
            dict.fromkeys(_entity_ids(entity.get("claims", {}).get(P_INFLUENCED_BY, [])))
        )
        labels = await self._labels(influence_ids)
        nodes = [
            InfluenceNode(qid=item, nome=labels[item], url=f"https://www.wikidata.org/wiki/{item}")
            for item in influence_ids
            if item in labels
        ]
        graph = InfluenceGraph(
            pensador=InfluenceNode(qid=qid, nome=nome, url=f"https://www.wikidata.org/wiki/{qid}"),
            influenciado_por=nodes,
            fonte=Attribution(
                fonte="Wikidata", licenca="CC0 1.0", url=f"https://www.wikidata.org/wiki/{qid}"
            ),
        )
        self._cache[key] = graph
        return graph
