"""Contratos da API (Pydantic v2, ADR-003). Fonte do schema OpenAPI."""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


class QuoteCategory(str, Enum):
    """Proveniência da frase, derivada da seção do Wikiquote (ver PILARES_TECNICOS.md)."""

    verificada = "verificada"
    obra = "obra"
    atribuida = "atribuida"


class Attribution(BaseModel):
    """Crédito obrigatório do conteúdo Wikimedia (ADR-015)."""

    fonte: str = Field(examples=["Wikiquote"])
    licenca: str = Field(examples=["CC BY-SA 4.0"])
    url: str | None = Field(default=None, examples=["https://pt.wikiquote.org/wiki/Albert_Camus"])


class TranslationCredit(BaseModel):
    """Responsabilidade e licença da tradução usada pelo catálogo."""

    responsavel: str
    licenca: str
    url: str | None = None


class PartialDate(BaseModel):
    """Data possivelmente parcial ou AEC (Wikidata usa `precision`)."""

    valor: str = Field(
        description="Ano/data ISO, negativo para AEC", examples=["1913-11-07", "-0544"]
    )
    precisao: str = Field(description="seculo | ano | mes | dia", examples=["dia"])
    exibicao: str = Field(description="Forma legível", examples=["07/11/1913", "século VI a.C."])


class Work(BaseModel):
    titulo: str = Field(examples=["O Mito de Sísifo"])
    qid: str | None = Field(default=None, examples=["Q1195005"])


class Quote(BaseModel):
    texto: str
    autor: str
    categoria: QuoteCategory
    obra: str | None = Field(default=None, description="Obra de origem, se a frase vier de uma")
    original: str | None = Field(default=None, description="Texto no idioma original, se houver")
    idioma_original: str | None = Field(
        default=None, description="Código BCP 47 do idioma do texto original"
    )
    traducao: TranslationCredit | None = Field(
        default=None, description="Crédito da tradução para o português, quando aplicável"
    )
    fonte: Attribution


class EditorialCollection(BaseModel):
    """Coleção editorial pequena e versionada junto com a aplicação."""

    slug: str
    titulo: str
    descricao: str
    pensadores: list[str]


class SelectionMode(str, Enum):
    daily = "daily"
    random = "random"


class QuoteSelection(BaseModel):
    """Frase selecionada e o contexto da regra que a escolheu."""

    frase: Quote
    modo: SelectionMode
    data: str | None = Field(default=None, description="Data UTC no modo diário")
    colecao: EditorialCollection | None = None


class CuratedQuoteSelection(QuoteSelection):
    """Seleção servida por um dataset curado e identificável."""

    dataset_version: str = Field(description="Versão da base curada")
    dataset_schema: int = Field(description="Versão do schema da base")


class Thinker(BaseModel):
    qid: str = Field(examples=["Q34670"])
    nome: str = Field(examples=["Albert Camus"])
    descricao: str | None = Field(default=None, examples=["filósofo e jornalista franco-argelino"])
    nascimento: PartialDate | None = None
    morte: PartialDate | None = None
    local_nascimento: str | None = Field(default=None, examples=["Dréan"])
    nacionalidade: list[str] = Field(default_factory=list)
    ocupacoes: list[str] = Field(default_factory=list)
    correntes: list[str] = Field(default_factory=list)
    formacao: list[str] = Field(default_factory=list)
    obras: list[Work] = Field(default_factory=list)
    fontes: list[Attribution] = Field(default_factory=list)


class ThinkerProfile(Thinker):
    """Perfil completo: biografia (Wikidata) + amostra de frases (Wikiquote)."""

    frases: list[Quote] = Field(default_factory=list)
    aviso: str | None = Field(default=None, description="Presente quando o perfil vem parcial")


class InfluenceNode(BaseModel):
    """Personalidade que influenciou o pensador consultado."""

    qid: str
    nome: str
    url: str


class InfluenceGraph(BaseModel):
    """Relação direta `influenciado por` (P737) registrada no Wikidata."""

    pensador: InfluenceNode
    influenciado_por: list[InfluenceNode]
    fonte: Attribution


class SearchHit(BaseModel):
    nome: str
    pagina: str = Field(description="Título da página no Wikiquote")


T = TypeVar("T")


class ListMeta(BaseModel):
    """Metadados de paginação de uma coleção (ADR-020)."""

    count: int = Field(description="Itens nesta resposta")
    limit: int
    offset: int = 0
    total: int | None = Field(default=None, description="Total disponível, quando conhecido")
    has_more: bool = Field(default=False, description="Há mais itens além desta página")


class Page(BaseModel, Generic[T]):
    """Envelope de coleção: `data` + `meta` (ADR-020). Recurso único vai 'cru'."""

    data: list[T]
    meta: ListMeta


class ProblemDetail(BaseModel):
    """Corpo de erro problem+json — RFC 9457 (ADR-007)."""

    type: str = Field(
        default="about:blank",
        description="URI que identifica o tipo do problema (RFC 9457)",
        examples=["/problems/thinker-not-found"],
    )
    title: str
    status: int
    detail: str | None = None
    instance: str | None = Field(
        default=None, description="URI da ocorrência específica (path da requisição)"
    )
