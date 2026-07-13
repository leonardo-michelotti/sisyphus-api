import json
import sqlite3
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest
import respx

from sisyphus.config import settings
from sisyphus.pipeline.build import (
    Snapshot,
    _fetch_one,
    _load_bronze,
    _source_record,
    audit,
    publish,
    transform,
)


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
            """select quote_text, curation_status, quality_reason, is_daily_eligible,
                      quality_reasons
               from fct_quotes"""
        ).fetchall()
        identities = con.execute(
            """select quote_id, occurrence_id, source_name, source_license
               from fct_quotes"""
        ).fetchall()
    actual = {text: (status, reason, eligible) for text, status, reason, eligible, _reasons in rows}

    for case in cases:
        assert actual[case["text"]] == (
            case["expected_status"],
            case["expected_reason"],
            case["daily_eligible"],
        ), case["decision"]

    reasons = {text: values for text, *_rest, values in rows}
    assert reasons["A sabedoria começa na reflexão."] == [
        "short_text",
        "attributed_quote",
    ]
    assert all(
        len(quote_id) == len(occurrence_id) == 64 for quote_id, occurrence_id, *_ in identities
    )
    assert {(source, license_) for *_, source, license_ in identities} == {
        ("Wikiquote", "CC BY-SA 4.0")
    }

    with sqlite3.connect(serving) as con:
        assert con.execute("pragma integrity_check").fetchone() == ("ok",)
        assert con.execute("select count(*) from quotes").fetchone() == (4,)
        assert con.execute(
            "select count(*) from quotes_fts where quotes_fts match 'velhice'"
        ).fetchone() == (1,)
        stored_reasons = con.execute(
            "select quality_reasons from quotes where quote_text = ?",
            ("A sabedoria começa na reflexão.",),
        ).fetchone()
        assert stored_reasons is not None
        assert json.loads(stored_reasons[0]) == ["short_text", "attributed_quote"]
        assert con.execute(
            "select distinct source_name, source_license from quotes"
        ).fetchall() == [("Wikiquote", "CC BY-SA 4.0")]

    assert metrics == {
        "total": 4,
        "thinkers": 1,
        "accepted": 1,
        "review": 2,
        "rejected": 1,
        "daily": 1,
    }
    assert "A base antes da frase" in report.read_text(encoding="utf-8")


def test_bronze_accepts_page_without_quotes(tmp_path: Path) -> None:
    warehouse = tmp_path / "sisyphus.duckdb"
    _load_bronze(
        [_snapshot("<div class='mw-parser-output'><p>Sem listas.</p></div>")],
        warehouse=warehouse,
        bronze_dir=tmp_path / "bronze",
    )

    with duckdb.connect(str(warehouse), read_only=True) as con:
        assert con.execute("select count(*) from bronze_thinkers").fetchone() == (1,)
        assert con.execute("select count(*) from bronze_quotes").fetchone() == (0,)


def test_failed_publication_preserves_current_database(tmp_path: Path) -> None:
    warehouse = tmp_path / "invalid.duckdb"
    serving = tmp_path / "sisyphus.db"
    serving.write_bytes(b"current production artifact")
    with duckdb.connect(str(warehouse)):
        pass

    with pytest.raises(duckdb.CatalogException):
        publish(warehouse=warehouse, serving=serving)

    assert serving.read_bytes() == b"current production artifact"
    assert not (tmp_path / ".sisyphus.db.next").exists()


def test_snapshot_sources_are_immutable_and_hashed(tmp_path: Path) -> None:
    item = _snapshot("<div>conteúdo</div>")
    record = _source_record(item, tmp_path)

    wikiquote_files = list((tmp_path / "wikiquote").glob("*.json"))
    wikidata_files = list((tmp_path / "wikidata").glob("*.json"))
    assert len(wikiquote_files) == len(wikidata_files) == 1
    assert record["wikiquote_file"] == f"wikiquote/{wikiquote_files[0].name}"
    assert record["wikidata_file"] == f"wikidata/{wikidata_files[0].name}"
    assert record["wikiquote_sha256"] in wikiquote_files[0].name
    assert record["wikidata_sha256"] in wikidata_files[0].name
    assert record["wikiquote_revision"] == 225583


@respx.mock
async def test_fetch_uses_revision_of_parsed_content() -> None:
    respx.get(settings.wikiquote_api).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "query": {
                        "pages": [
                            {
                                "title": "Sócrates",
                                "pageprops": {"wikibase_item": "Q913"},
                            }
                        ]
                    }
                },
            ),
            httpx.Response(200, json={"parse": {"revid": 42, "text": "<div />"}}),
        ]
    )
    respx.get(settings.wikidata_api).mock(
        return_value=httpx.Response(200, json={"entities": {"Q913": {}}})
    )

    async with httpx.AsyncClient() as client:
        snapshot = await _fetch_one(client, "Sócrates")

    assert snapshot.revision == 42


@respx.mock
async def test_fetch_rejects_payload_without_parsed_revision() -> None:
    respx.get(settings.wikiquote_api).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "query": {
                        "pages": [
                            {
                                "title": "Sócrates",
                                "pageprops": {"wikibase_item": "Q913"},
                            }
                        ]
                    }
                },
            ),
            httpx.Response(200, json={"parse": {"text": "<div />"}}),
        ]
    )
    respx.get(settings.wikidata_api).mock(
        return_value=httpx.Response(200, json={"entities": {"Q913": {}}})
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="sem revisão"):
            await _fetch_one(client, "Sócrates")
