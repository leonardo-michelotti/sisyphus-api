"""Client do Wikiquote PT.

- Resolução nome -> página + QID (`list=search` + `pageprops`, ADR-018).
- Frases a partir do HTML renderizado + lxml + denylist (ADR-016).

A extração é uma função pura (`parse_quotes`) para ser testável sem rede.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, cast

import httpx
from cachetools import TTLCache
from lxml.html import HtmlElement, fromstring

from ..config import settings
from ..errors import ThinkerNotFound, UpstreamError, UpstreamTimeout
from ..schemas import Attribution, Quote, QuoteCategory, SearchHit

# Seções que NÃO são frases do autor (ADR-016). Armadilha principal: "Sobre".
_DENY = {
    "sobre",
    "ligações externas",
    "ver também",
    "referências",
    "notas",
    "bibliografia",
    "fontes",
}
_LICENSE = "CC BY-SA 4.0"


def _section_base(title: str) -> str:
    """Normaliza o título da seção para comparação: minúsculas, sem sufixo (ano)."""
    return re.sub(r"\s*\(.*?\)\s*$", "", title).strip().lower()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _categoria(section: str) -> tuple[QuoteCategory, str | None]:
    base = _section_base(section)
    if base in ("verificadas", "topo", ""):
        return QuoteCategory.verificada, None
    if base in ("atribuídas", "atribuidas"):
        return QuoteCategory.atribuida, None
    return QuoteCategory.obra, section


def _page_url(title: str) -> str:
    return "https://pt.wikiquote.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def parse_quotes(html: str, autor: str, page_url: str) -> list[Quote]:
    """Extrai as frases do HTML renderizado do Wikiquote (função pura)."""
    doc = fromstring(html)
    roots = cast(list[HtmlElement], doc.xpath("//div[contains(@class,'mw-parser-output')]"))
    root: HtmlElement = roots[0] if roots else doc

    quotes: list[Quote] = []
    section = "(topo)"
    skip = False
    fonte = Attribution(fonte="Wikiquote", licenca=_LICENSE, url=page_url)

    for el in root.iterchildren():
        el = cast(HtmlElement, el)
        heads: list[HtmlElement] = (
            cast(list[HtmlElement], el.xpath(".//h2|.//h3|.//h4"))
            if el.tag == "div"
            else ([el] if el.tag in ("h2", "h3", "h4") else [])
        )
        if heads:
            section = _norm(heads[0].text_content())
            skip = _section_base(section) in _DENY
            continue
        if skip or el.tag != "ul":
            continue
        for li in el.findall("li"):
            # texto do <li> excluindo sublistas aninhadas (fonte/original vivem em ul/dl)
            parts = cast(
                list[str], li.xpath("./text() | ./*[not(self::ul) and not(self::dl)]//text()")
            )
            texto = _norm("".join(parts)).strip('"“”').strip()
            if len(texto) < 8:
                continue
            categoria, obra = _categoria(section)
            quotes.append(
                Quote(texto=texto, autor=autor, categoria=categoria, obra=obra, fonte=fonte)
            )
    return quotes


class WikiquoteClient:
    def __init__(self, http: httpx.AsyncClient, cache: TTLCache[str, Any]) -> None:
        self._http = http
        self._cache = cache

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "format": "json", "formatversion": "2"}
        try:
            resp = await self._http.get(settings.wikiquote_api, params=params)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise UpstreamTimeout("Wikiquote não respondeu a tempo") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Falha ao consultar o Wikiquote: {exc}") from exc
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("Wikiquote devolveu uma resposta inválida") from exc
        if not isinstance(data, dict):
            raise UpstreamError("Wikiquote devolveu um payload inesperado")
        return data

    async def search(self, q: str, limit: int = 5) -> list[SearchHit]:
        data = await self._get(
            {"action": "query", "list": "search", "srsearch": q, "srnamespace": 0, "srlimit": limit}
        )
        hits = data.get("query", {}).get("search", [])
        if not isinstance(hits, list):
            raise UpstreamError("Wikiquote devolveu uma busca inválida")
        return [
            SearchHit(nome=title, pagina=title)
            for hit in hits
            if isinstance(hit, dict) and isinstance((title := hit.get("title")), str)
        ]

    async def resolve(self, nome: str) -> tuple[str, str]:
        """Nome vago -> (título canônico, QID). Levanta ThinkerNotFound se não achar."""
        key = f"resolve:{nome.lower()}"
        if key in self._cache:
            return self._cache[key]  # type: ignore[no-any-return]

        hits = await self.search(nome, limit=1)
        if not hits:
            raise ThinkerNotFound(f"Nenhum pensador encontrado para {nome!r}")
        titulo = hits[0].pagina

        data = await self._get(
            {"action": "query", "titles": titulo, "prop": "pageprops", "redirects": 1}
        )
        pages = data.get("query", {}).get("pages", [])
        if not isinstance(pages, list) or not pages or not isinstance(pages[0], dict):
            raise UpstreamError("Wikiquote devolveu uma resolução inválida")
        if pages[0].get("missing"):
            raise ThinkerNotFound(f"Página inexistente para {nome!r}")
        page = pages[0]
        qid = page.get("pageprops", {}).get("wikibase_item")
        if not qid:
            raise ThinkerNotFound(f"{page.get('title', nome)!r} não tem entidade no Wikidata")

        result = (page["title"], qid)
        self._cache[key] = result
        return result

    async def get_quotes(self, titulo: str) -> list[Quote]:
        key = f"quotes:{titulo}"
        if key in self._cache:
            return self._cache[key]  # type: ignore[no-any-return]

        data = await self._get({"action": "parse", "page": titulo, "prop": "text"})
        if "error" in data:
            raise ThinkerNotFound(f"Sem página de frases para {titulo!r}")
        parsed = data.get("parse")
        html = parsed.get("text") if isinstance(parsed, dict) else None
        if not isinstance(html, str):
            raise UpstreamError("Wikiquote devolveu uma página de frases inválida")
        try:
            quotes = parse_quotes(html, autor=titulo, page_url=_page_url(titulo))
        except (TypeError, ValueError) as exc:
            raise UpstreamError("Não foi possível interpretar a página do Wikiquote") from exc
        self._cache[key] = quotes
        return quotes
