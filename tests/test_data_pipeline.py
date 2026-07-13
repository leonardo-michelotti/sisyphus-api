import asyncio
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import duckdb
import httpx
import pytest
import respx

from sisyphus.config import settings
from sisyphus.pipeline import build
from sisyphus.pipeline.build import (
    Snapshot,
    _dataset_version,
    _fetch_one,
    _get_with_retry,
    _load_bronze,
    _record_build_provenance,
    _source_record,
    audit,
    ingest,
    publish,
    transform,
)
from sisyphus.repositories.quotes import SQLiteQuoteRepository


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
    _record_build_provenance(
        warehouse,
        run_id="fixture-run",
        manifest_sha256="a" * 64,
    )
    transform(warehouse=warehouse)
    publish(warehouse=warehouse, serving=serving, expected_thinkers={"Sócrates"})
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
        metadata = con.execute("select * from build_metadata").fetchone()
        assert metadata is not None
        assert metadata[0] == 2
        assert len(metadata[1]) == 16
        assert metadata[3:] == ("2", "1", "fixture-run", "a" * 64, "local")
        assert con.execute("select count(*) from quotes").fetchone() == (5,)
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

    selection = SQLiteQuoteRepository(serving).select(thinker="Sócrates", on_date=date(2026, 7, 13))
    assert selection.frase.texto == (
        "A admiração é o sentimento de um filósofo, e a filosofia começa pela admiração."
    )
    assert selection.dataset_version == metadata[1]

    assert metrics == {
        "total": 5,
        "thinkers": 1,
        "accepted": 2,
        "review": 2,
        "rejected": 1,
        "daily": 1,
    }
    assert "A base antes da frase" in report.read_text(encoding="utf-8")


def test_bronze_accepts_page_without_quotes(tmp_path: Path) -> None:
    warehouse = tmp_path / "sisyphus.duckdb"
    _record_build_provenance(warehouse, run_id="old", manifest_sha256="b" * 64)
    _load_bronze(
        [_snapshot("<div class='mw-parser-output'><p>Sem listas.</p></div>")],
        warehouse=warehouse,
        bronze_dir=tmp_path / "bronze",
    )

    with duckdb.connect(str(warehouse), read_only=True) as con:
        assert con.execute("select count(*) from bronze_thinkers").fetchone() == (1,)
        assert con.execute("select count(*) from bronze_quotes").fetchone() == (0,)
        with pytest.raises(duckdb.CatalogException):
            con.execute("select * from pipeline_build_metadata")


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


@respx.mock
async def test_http_retries_only_transient_failures() -> None:
    route = respx.get("https://example.test/source").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    sleep = AsyncMock()

    with patch("sisyphus.pipeline.build.asyncio.sleep", sleep):
        async with httpx.AsyncClient() as client:
            response = await _get_with_retry(client, "https://example.test/source", params={})

    assert response.json() == {"ok": True}
    assert route.call_count == 3
    assert sleep.await_count == 2
    assert sleep.await_args_list[1].args == (0.0,)


@respx.mock
async def test_http_does_not_retry_permanent_failure() -> None:
    route = respx.get("https://example.test/missing").mock(return_value=httpx.Response(404))
    sleep = AsyncMock()

    with patch("sisyphus.pipeline.build.asyncio.sleep", sleep):
        async with httpx.AsyncClient() as client:
            with pytest.raises(httpx.HTTPStatusError):
                await _get_with_retry(client, "https://example.test/missing", params={})

    assert route.call_count == 1
    sleep.assert_not_awaited()


def _named_snapshot(name: str, index: int) -> Snapshot:
    return Snapshot(
        name=name,
        title=name,
        qid=f"Q{index}",
        revision=index,
        fetched_at="2026-07-13T12:00:00+00:00",
        wikiquote={"parse": {"revid": index, "text": "<div />"}},
        wikidata={"entities": {f"Q{index}": {}}},
    )


async def test_ingest_limits_concurrency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    names = tuple(f"Thinker {index}" for index in range(8))
    active = 0
    maximum = 0

    async def fake_fetch(_client: httpx.AsyncClient, name: str) -> Snapshot:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return _named_snapshot(name, names.index(name) + 1)

    monkeypatch.setattr(build, "ALL_THINKERS", names)
    monkeypatch.setattr(build, "_fetch_one", fake_fetch)

    snapshots = await ingest(
        bronze_root=tmp_path / "bronze",
        warehouse=tmp_path / "warehouse.duckdb",
        run_id="limited",
        concurrency=4,
    )

    assert len(snapshots) == 8
    assert maximum == 4
    manifest_path = tmp_path / "bronze" / "limited" / "manifest.json"
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    with duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True) as connection:
        assert connection.execute(
            """select run_id, manifest_sha256, pipeline_version,
                      parser_version, source_commit
               from pipeline_build_metadata"""
        ).fetchone() == ("limited", manifest_sha256, "2", "1", "local")


async def test_failed_source_is_visible_in_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    names = ("Available", "Unavailable")

    async def fake_fetch(_client: httpx.AsyncClient, name: str) -> Snapshot:
        if name == "Unavailable":
            raise httpx.ConnectError("offline")
        return _named_snapshot(name, 1)

    monkeypatch.setattr(build, "ALL_THINKERS", names)
    monkeypatch.setattr(build, "_fetch_one", fake_fetch)

    with pytest.raises(RuntimeError, match="warehouse não foi atualizado"):
        await ingest(
            bronze_root=tmp_path / "bronze",
            warehouse=tmp_path / "warehouse.duckdb",
            run_id="failed",
        )

    manifest = json.loads(
        (tmp_path / "bronze" / "failed" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "failed"
    assert [(item["requested_name"], item["status"]) for item in manifest["sources"]] == [
        ("Available", "success"),
        ("Unavailable", "failed"),
    ]
    assert manifest["sources"][1]["error"] == "ConnectError"


def _create_publication_warehouse(path: Path, *, eligible: bool) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute(
            """create table dim_thinkers as select
               'Q913'::varchar thinker_qid, 'Sócrates'::varchar thinker_name,
               'Sócrates'::varchar wikiquote_title, 'https://example.test'::varchar source_url,
               1::bigint source_revision, current_timestamp fetched_at"""
        )
        con.execute(
            """create table fct_quotes as select
               'occurrence'::varchar occurrence_id, 'quote'::varchar quote_id,
               'Q913'::varchar thinker_qid,
               'Uma frase suficientemente longa para publicação.'::varchar quote_text,
               'verificada'::varchar category, null::varchar as work,
               'https://example.test'::varchar source_url, 'Wikiquote'::varchar source_name,
               'CC BY-SA 4.0'::varchar source_license, 1::bigint source_revision,
               45::integer character_count, 'accepted'::varchar curation_status,
               'passed_automatic_rules'::varchar quality_reason,
               ['passed_automatic_rules']::varchar[] quality_reasons,
               ?::boolean is_daily_eligible""",
            [eligible],
        )


def test_dataset_version_covers_all_serving_fields() -> None:
    thinkers = [("Q1", "Nome", "Título", "https://example.test", 1)]
    quote = (
        "occurrence",
        "quote",
        "Q1",
        "Uma frase suficientemente longa para publicação.",
        "verificada",
        None,
        "https://example.test",
        "Wikiquote",
        "CC BY-SA 4.0",
        1,
        48,
        "accepted",
        "passed_automatic_rules",
        '["passed_automatic_rules"]',
        1,
    )

    original = _dataset_version(thinkers, [quote])
    changed_license = _dataset_version(thinkers, [(*quote[:8], "CC BY-SA 5.0", *quote[9:])])
    changed_thinker = _dataset_version(
        [("Q1", "Outro nome", "Título", "https://example.test", 1)], [quote]
    )

    assert original != changed_license
    assert original != changed_thinker


@pytest.mark.parametrize(
    ("eligible", "expected", "message"),
    [
        (False, {"Sócrates"}, "nenhuma frase elegível"),
        (True, {"Sócrates", "Albert Camus"}, "pensadores ausentes: Albert Camus"),
    ],
)
def test_publication_gates_preserve_current_database(
    tmp_path: Path, eligible: bool, expected: set[str], message: str
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    serving = tmp_path / "sisyphus.db"
    serving.write_bytes(b"current production artifact")
    _create_publication_warehouse(warehouse, eligible=eligible)

    with pytest.raises(RuntimeError, match=message):
        publish(warehouse=warehouse, serving=serving, expected_thinkers=expected)

    assert serving.read_bytes() == b"current production artifact"
