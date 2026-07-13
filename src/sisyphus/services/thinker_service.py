"""Orquestra o perfil de um pensador a partir das duas fontes.

Resolve nome -> (título, QID) no Wikiquote e então busca bio (Wikidata) e frases
(Wikiquote) de forma **concorrente** (ADR-004). Tolera perfil parcial: se as
frases falharem mas a bio vier, devolve o perfil com um `aviso` (ADR-007).
"""

from __future__ import annotations

import asyncio
import logging

from ..clients.wikidata import WikidataClient
from ..clients.wikiquote import WikiquoteClient
from ..errors import SisyphusError, UpstreamError
from ..schemas import InfluenceGraph, Quote, SearchHit, ThinkerProfile

logger = logging.getLogger(__name__)


class ThinkerService:
    def __init__(self, wikiquote: WikiquoteClient, wikidata: WikidataClient) -> None:
        self._wq = wikiquote
        self._wd = wikidata

    async def search(self, q: str, limit: int = 5) -> list[SearchHit]:
        return await self._wq.search(q, limit=limit)

    async def get_quotes(self, nome: str) -> list[Quote]:
        titulo, _ = await self._wq.resolve(nome)
        return await self._wq.get_quotes(titulo)

    async def get_influences(self, nome: str) -> InfluenceGraph:
        titulo, qid = await self._wq.resolve(nome)
        return await self._wd.get_influences(qid, titulo)

    async def get_profile(self, nome: str, sample: int = 10) -> ThinkerProfile:
        titulo, qid = await self._wq.resolve(nome)

        bio, frases = await asyncio.gather(
            self._wd.get_profile(qid, nome=titulo),
            self._wq.get_quotes(titulo),
            return_exceptions=True,
        )

        # A bio é o núcleo do perfil: se falhar, propaga o erro upstream.
        if isinstance(bio, BaseException):
            if isinstance(bio, SisyphusError):
                raise bio
            raise UpstreamError(f"Falha ao montar a biografia: {bio}")

        aviso: str | None = None
        lista_frases: list[Quote] = []
        fontes = list(bio.fontes)
        if isinstance(frases, BaseException):
            logger.warning("Frases indisponíveis para %s: %s", titulo, frases)
            aviso = "Frases indisponíveis no momento; perfil parcial (biografia apenas)."
        else:
            lista_frases = frases[:sample]
            if lista_frases:
                fontes.append(lista_frases[0].fonte)  # crédito Wikiquote no nível do perfil

        dados = bio.model_dump()
        dados["fontes"] = [f.model_dump() for f in fontes]
        return ThinkerProfile(**dados, frases=lista_frases, aviso=aviso)
