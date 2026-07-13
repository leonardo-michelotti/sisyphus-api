"""Leitura pequena e somente leitura do catálogo publicado em SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Collection
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from ..catalog import ALL_THINKERS, get_collection
from ..dataset import SERVING_SCHEMA_VERSION
from ..errors import DatasetUnavailable, InvalidSelection, NoQuotesAvailable, ThinkerNotFound
from ..schemas import Attribution, CuratedQuoteSelection, Quote, QuoteCategory, SelectionMode


class DailyQuoteRepository(Protocol):
    def select(
        self,
        *,
        thinker: str | None = None,
        collection_slug: str | None = None,
        category: QuoteCategory | None = None,
        max_length: int | None = None,
        on_date: date | None = None,
    ) -> CuratedQuoteSelection: ...


def _seed(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], byteorder="big")


class SQLiteQuoteRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(f"file:{self._path.resolve()}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise DatasetUnavailable("Base curada ausente ou ilegível") from exc
        connection.row_factory = sqlite3.Row
        return connection

    def metadata(self) -> tuple[int, str]:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "select schema_version, dataset_version from build_metadata"
                ).fetchone()
        except sqlite3.Error as exc:
            raise DatasetUnavailable("Metadados da base curada estão ausentes") from exc
        if row is None or row["schema_version"] != SERVING_SCHEMA_VERSION:
            raise DatasetUnavailable("Versão incompatível da base curada")
        version = row["dataset_version"]
        if not isinstance(version, str) or not version:
            raise DatasetUnavailable("Versão da base curada está ausente")
        return SERVING_SCHEMA_VERSION, version

    def is_ready(self) -> bool:
        try:
            self.metadata()
        except DatasetUnavailable:
            return False
        return True

    def select(
        self,
        *,
        thinker: str | None = None,
        collection_slug: str | None = None,
        category: QuoteCategory | None = None,
        max_length: int | None = None,
        on_date: date | None = None,
    ) -> CuratedQuoteSelection:
        collection = get_collection(collection_slug) if collection_slug else None
        if thinker and thinker not in ALL_THINKERS:
            raise ThinkerNotFound(f"Pensador {thinker!r} não pertence ao catálogo diário")
        if thinker and collection and thinker not in collection.pensadores:
            raise InvalidSelection(f"{thinker!r} não pertence à coleção {collection.titulo!r}")
        candidates: Collection[str] = (
            [thinker] if thinker else collection.pensadores if collection else ALL_THINKERS
        )
        selected_date = on_date or datetime.now(timezone.utc).date()
        schema_version, dataset_version = self.metadata()

        placeholders = ", ".join("?" for _ in candidates)
        clauses = ["q.is_daily_eligible = 1", f"t.thinker_name in ({placeholders})"]
        parameters: list[object] = list(candidates)
        if category is not None:
            clauses.append("q.category = ?")
            parameters.append(category.value)
        if max_length is not None:
            clauses.append("q.character_count <= ?")
            parameters.append(max_length)

        query = f"""select q.occurrence_id, q.quote_text, t.thinker_name, q.category,
                           q.work, q.source_name, q.source_license, q.source_url
                    from quotes q
                    join thinkers t on t.thinker_qid = q.thinker_qid
                    where {" and ".join(clauses)}
                    order by q.occurrence_id"""
        try:
            with self._connect() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as exc:
            raise DatasetUnavailable("Schema da base curada é incompatível") from exc
        if not rows:
            raise NoQuotesAvailable("Nenhuma frase curada corresponde aos filtros informados")

        key = "|".join(
            [
                dataset_version,
                selected_date.isoformat(),
                thinker or "",
                collection_slug or "",
                category.value if category else "",
                str(max_length or ""),
            ]
        )
        row = rows[_seed(key) % len(rows)]
        return CuratedQuoteSelection(
            frase=Quote(
                texto=row["quote_text"],
                autor=row["thinker_name"],
                categoria=QuoteCategory(row["category"]),
                obra=row["work"],
                fonte=Attribution(
                    fonte=row["source_name"],
                    licenca=row["source_license"],
                    url=row["source_url"],
                ),
            ),
            modo=SelectionMode.daily,
            data=selected_date.isoformat(),
            colecao=collection,
            dataset_version=dataset_version,
            dataset_schema=schema_version,
        )
