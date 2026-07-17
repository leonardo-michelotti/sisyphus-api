"""Auditoria reproduzível da cobertura editorial do SQLite publicado."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from .catalog import DAILY_QUOTES_PER_THINKER, list_collections
from .repositories.quotes import SQLiteQuoteRepository


@dataclass(frozen=True)
class CollectionCoverage:
    slug: str
    titulo: str
    pensadores: int
    pensadores_cobertos: int
    frases_elegiveis: int
    fontes_completas: int
    obras_identificadas: int
    tamanho_minimo: int
    tamanho_medio: float
    tamanho_maximo: int
    pensadores_sem_frase: tuple[str, ...]


@dataclass(frozen=True)
class CollectionAudit:
    dataset_version: str
    total_registros: int
    frases_elegiveis: int
    pensadores: int
    textos_duplicados: int
    frases_por_pensador_minimo: int
    frases_por_pensador_maximo: int
    colecoes: tuple[CollectionCoverage, ...]

    @property
    def cobertura_completa(self) -> bool:
        return (
            all(not item.pensadores_sem_frase for item in self.colecoes)
            and self.frases_por_pensador_minimo == DAILY_QUOTES_PER_THINKER
            and self.frases_por_pensador_maximo == DAILY_QUOTES_PER_THINKER
        )


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def audit_collections(path: Path) -> CollectionAudit:
    """Lê a base em modo somente leitura e mede o recorte diário por coleção."""
    metadata = SQLiteQuoteRepository(path).metadata()
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        total_records = connection.execute("select count(*) from quotes").fetchone()[0]
        thinker_count = connection.execute("select count(*) from thinkers").fetchone()[0]
        rows = connection.execute(
            """select t.thinker_name, q.quote_text, q.character_count, q.work,
                      q.source_name, q.source_license, q.source_url
               from quotes q
               join thinkers t on t.thinker_qid = q.thinker_qid
               where q.is_daily_eligible = 1
               order by t.thinker_name, q.occurrence_id"""
        ).fetchall()
    finally:
        connection.close()

    repetitions: dict[str, int] = {}
    for row in rows:
        key = _normalized(row["quote_text"])
        repetitions[key] = repetitions.get(key, 0) + 1

    quotes_per_thinker: dict[str, int] = {}
    for row in rows:
        name = str(row["thinker_name"])
        quotes_per_thinker[name] = quotes_per_thinker.get(name, 0) + 1

    coverages: list[CollectionCoverage] = []
    for collection in list_collections():
        names = set(collection.pensadores)
        collection_rows = [row for row in rows if row["thinker_name"] in names]
        covered = {row["thinker_name"] for row in collection_rows}
        lengths = [int(row["character_count"]) for row in collection_rows]
        sources = sum(
            bool(row["source_name"] and row["source_license"] and row["source_url"])
            for row in collection_rows
        )
        works = sum(bool(row["work"]) for row in collection_rows)
        coverages.append(
            CollectionCoverage(
                slug=collection.slug,
                titulo=collection.titulo,
                pensadores=len(collection.pensadores),
                pensadores_cobertos=len(covered),
                frases_elegiveis=len(collection_rows),
                fontes_completas=sources,
                obras_identificadas=works,
                tamanho_minimo=min(lengths, default=0),
                tamanho_medio=round(sum(lengths) / len(lengths), 1) if lengths else 0.0,
                tamanho_maximo=max(lengths, default=0),
                pensadores_sem_frase=tuple(sorted(names - covered)),
            )
        )

    return CollectionAudit(
        dataset_version=metadata.dataset_version,
        total_registros=int(total_records),
        frases_elegiveis=len(rows),
        pensadores=int(thinker_count),
        textos_duplicados=sum(count - 1 for count in repetitions.values() if count > 1),
        frases_por_pensador_minimo=min(quotes_per_thinker.values(), default=0),
        frases_por_pensador_maximo=max(quotes_per_thinker.values(), default=0),
        colecoes=tuple(coverages),
    )


def render_markdown(report: CollectionAudit) -> str:
    status = "completa" if report.cobertura_completa else "com lacunas"
    lines = [
        "# Auditoria das coleções editoriais",
        "",
        f"Dataset `{report.dataset_version}`. Cobertura diária **{status}**.",
        "",
        f"- {report.total_registros} registros coletados;",
        f"- {report.frases_elegiveis} frases aprovadas para o modo diário;",
        f"- {report.pensadores} pensadores;",
        f"- {report.frases_por_pensador_minimo} a "
        f"{report.frases_por_pensador_maximo} frases por pensador;",
        f"- {report.textos_duplicados} textos duplicados no recorte diário.",
        "",
        "| Coleção | Cobertura | Frases | Fontes | Com obra | Tamanho min./méd./máx. |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report.colecoes:
        average = f"{item.tamanho_medio:g}".replace(".", ",")
        lines.append(
            f"| {item.titulo} | {item.pensadores_cobertos}/{item.pensadores} | "
            f"{item.frases_elegiveis} | {item.fontes_completas} | "
            f"{item.obras_identificadas} | {item.tamanho_minimo}/{average}/"
            f"{item.tamanho_maximo} |"
        )
    gaps = [
        f"{item.titulo}: {', '.join(item.pensadores_sem_frase)}"
        for item in report.colecoes
        if item.pensadores_sem_frase
    ]
    if gaps:
        lines.extend(["", "## Lacunas", "", *[f"- {gap}" for gap in gaps]])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/sisyphus.db"))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    report = audit_collections(args.database)
    if args.format == "json":
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")


if __name__ == "__main__":
    main()
