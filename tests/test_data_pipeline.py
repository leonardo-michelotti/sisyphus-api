import json
import sqlite3
from pathlib import Path
from typing import Any

import duckdb

from sisyphus.pipeline.build import Snapshot, _load_bronze, audit, publish, transform


def _snapshot(html: str) -> Snapshot:
    return Snapshot(
        name="Sócrates",
        title="Sócrates",
        qid="Q913",
        revision=225583,
        fetched_at="2026-07-13T12:00:00+00:00",
        wikiquote={"parse": {"revid": 225583, "text": html}},
        wikidata={"entities": {"Q913": {}}},
    )


def test_pipeline_classifies_editorial_corpus(tmp_path: Path, fixtures_dir: Path) -> None:
    warehouse = tmp_path / "sisyphus.duckdb"
    serving = tmp_path / "sisyphus.db"
    report = tmp_path / "data-quality.html"
    html = (fixtures_dir / "socrates_edge_cases.html").read_text(encoding="utf-8")
    cases: list[dict[str, Any]] = json.loads(
        (fixtures_dir / "editorial_cases.json").read_text(encoding="utf-8")
    )

    _load_bronze([_snapshot(html)], warehouse=warehouse, bronze_dir=tmp_path / "bronze")
    transform(warehouse=warehouse)
    publish(warehouse=warehouse, serving=serving)
    metrics = audit(warehouse=warehouse, report=report)

    with duckdb.connect(str(warehouse), read_only=True) as con:
        rows = con.execute(
            """select quote_text, curation_status, quality_reason, is_daily_eligible
               from fct_quotes"""
        ).fetchall()
    actual = {text: (status, reason, eligible) for text, status, reason, eligible in rows}

    for case in cases:
        assert actual[case["text"]] == (
            case["expected_status"],
            case["expected_reason"],
            case["daily_eligible"],
        ), case["decision"]

    with sqlite3.connect(serving) as con:
        assert con.execute("pragma integrity_check").fetchone() == ("ok",)
        assert con.execute("select count(*) from quotes").fetchone() == (4,)
        assert con.execute(
            "select count(*) from quotes_fts where quotes_fts match 'velhice'"
        ).fetchone() == (1,)

    assert metrics == {
        "total": 4,
        "thinkers": 1,
        "accepted": 1,
        "review": 2,
        "rejected": 1,
        "daily": 1,
    }
    assert "A base antes da frase" in report.read_text(encoding="utf-8")
