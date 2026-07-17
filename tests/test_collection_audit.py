import sqlite3
from pathlib import Path

from sisyphus.audit import audit_collections, render_markdown
from sisyphus.catalog import ALL_THINKERS, DAILY_QUOTES_PER_THINKER


def _database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """create table build_metadata (
                schema_version integer not null,
                dataset_version text not null,
                source_fetched_at text not null,
                pipeline_version text not null,
                parser_version text not null,
                run_id text not null,
                manifest_sha256 text not null,
                source_commit text not null
            );
            create table thinkers (
                thinker_qid text primary key,
                thinker_name text not null
            );
            create table quotes (
                occurrence_id text primary key,
                thinker_qid text not null,
                quote_text text not null,
                character_count integer not null,
                work text,
                source_name text not null,
                source_license text not null,
                source_url text not null,
                is_daily_eligible integer not null
            );"""
        )
        connection.execute(
            """insert into build_metadata values (
                2, '0123456789abcdef', '2026-07-16T12:00:00Z',
                '2', '1', 'run-test', ?, 'commit-test'
            )""",
            ["a" * 64],
        )
        thinkers = [(f"Q{index}", name) for index, name in enumerate(ALL_THINKERS, start=1)]
        connection.executemany("insert into thinkers values (?, ?)", thinkers)
        connection.executemany(
            "insert into quotes values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f"occ-{index}-{quote_number}",
                    qid,
                    f"Frase editorial número {index}-{quote_number} para auditoria.",
                    44,
                    "Obra" if index % 2 == 0 else None,
                    "Wikiquote",
                    "CC BY-SA 4.0",
                    f"https://example.test/{index}",
                    1,
                )
                for index, (qid, _name) in enumerate(thinkers, start=1)
                for quote_number in range(1, DAILY_QUOTES_PER_THINKER + 1)
            ],
        )
    return path


def test_audit_reports_complete_collection_coverage(tmp_path: Path) -> None:
    report = audit_collections(_database(tmp_path / "sisyphus.db"))

    assert report.cobertura_completa
    assert report.frases_elegiveis == len(ALL_THINKERS) * DAILY_QUOTES_PER_THINKER == 54
    assert report.frases_por_pensador_minimo == DAILY_QUOTES_PER_THINKER
    assert report.frases_por_pensador_maximo == DAILY_QUOTES_PER_THINKER
    assert report.textos_duplicados == 0
    assert len(report.colecoes) == 10
    assert all(item.pensadores_cobertos == item.pensadores == 4 for item in report.colecoes)
    assert all(item.fontes_completas == item.frases_elegiveis for item in report.colecoes)


def test_audit_exposes_collection_gaps(tmp_path: Path) -> None:
    path = _database(tmp_path / "sisyphus.db")
    with sqlite3.connect(path) as connection:
        connection.execute(
            """update quotes set is_daily_eligible = 0
               where thinker_qid = (select thinker_qid from thinkers where thinker_name = ?)""",
            ["Albert Camus"],
        )

    report = audit_collections(path)
    markdown = render_markdown(report)

    assert not report.cobertura_completa
    assert "Albert Camus" in markdown
    assert "Cobertura diária **com lacunas**" in markdown
