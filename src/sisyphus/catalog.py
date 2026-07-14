"""Catálogo editorial inicial do Sisyphus.

O catálogo é pequeno de propósito: oferece uma experiência confiável antes de
introduzir banco, painel administrativo ou coleções criadas por usuários.
"""

from __future__ import annotations

from .errors import CollectionNotFound
from .schemas import EditorialCollection

_COLLECTIONS = (
    EditorialCollection(
        slug="existencia-e-absurdo",
        titulo="Existência e absurdo",
        descricao="Liberdade, sentido e a experiência de existir.",
        pensadores=[
            "Albert Camus",
            "Friedrich Nietzsche",
            "Jean-Paul Sartre",
            "Simone de Beauvoir",
        ],
    ),
    EditorialCollection(
        slug="ciencia-e-curiosidade",
        titulo="Ciência e curiosidade",
        descricao="Investigação, descoberta e os limites do conhecimento.",
        pensadores=["Carl Sagan", "Marie Curie", "Albert Einstein", "Richard Feynman"],
    ),
    EditorialCollection(
        slug="liberdade-e-responsabilidade",
        titulo="Liberdade e responsabilidade",
        descricao="Escolhas individuais, ação política e responsabilidade pelo mundo.",
        pensadores=["Hannah Arendt", "Simone de Beauvoir", "John Stuart Mill", "Nelson Mandela"],
    ),
    EditorialCollection(
        slug="sociedade-e-poder",
        titulo="Sociedade e poder",
        descricao="Estruturas sociais, autoridade, conflito e transformação.",
        pensadores=["Hannah Arendt", "Michel Foucault", "Karl Marx", "Max Weber"],
    ),
    EditorialCollection(
        slug="conhecimento-e-duvida",
        titulo="Conhecimento e dúvida",
        descricao="Razão, método, incerteza e pensamento crítico.",
        pensadores=["Sócrates", "René Descartes", "Bertrand Russell", "Karl Popper"],
    ),
    EditorialCollection(
        slug="trabalho-e-vocacao",
        titulo="Trabalho e vocação",
        descricao="Trabalho, ação e os sentidos da vida pública.",
        pensadores=["Karl Marx", "Max Weber", "Hannah Arendt", "Simone de Beauvoir"],
    ),
    EditorialCollection(
        slug="revolta-e-resistencia",
        titulo="Revolta e resistência",
        descricao="Recusa, coragem e transformação do mundo comum.",
        pensadores=["Albert Camus", "Nelson Mandela", "Hannah Arendt", "Simone de Beauvoir"],
    ),
    EditorialCollection(
        slug="metodo-e-descoberta",
        titulo="Método e descoberta",
        descricao="Dúvida, experimento e construção do conhecimento.",
        pensadores=["René Descartes", "Karl Popper", "Marie Curie", "Richard Feynman"],
    ),
    EditorialCollection(
        slug="universo-e-humanidade",
        titulo="Universo e humanidade",
        descricao="Cosmos, ciência e o lugar humano no desconhecido.",
        pensadores=["Carl Sagan", "Albert Einstein", "Richard Feynman", "Bertrand Russell"],
    ),
    EditorialCollection(
        slug="individuo-e-liberdade",
        titulo="Indivíduo e liberdade",
        descricao="Autonomia, escolha e convivência com o outro.",
        pensadores=[
            "John Stuart Mill",
            "Friedrich Nietzsche",
            "Jean-Paul Sartre",
            "Nelson Mandela",
        ],
    ),
)

COLLECTIONS: dict[str, EditorialCollection] = {item.slug: item for item in _COLLECTIONS}
ALL_THINKERS: tuple[str, ...] = tuple(
    dict.fromkeys(thinker for item in _COLLECTIONS for thinker in item.pensadores)
)


def list_collections() -> list[EditorialCollection]:
    return list(_COLLECTIONS)


def get_collection(slug: str) -> EditorialCollection:
    try:
        return COLLECTIONS[slug]
    except KeyError as exc:
        raise CollectionNotFound(f"Coleção {slug!r} não existe") from exc
