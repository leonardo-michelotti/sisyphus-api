import sqlite3
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from sisyphus.config import settings
from sisyphus.errors import (
    DatasetUnavailable,
    InvalidSelection,
    NoQuotesAvailable,
    ThinkerNotFound,
)
from sisyphus.main import create_app
from sisyphus.repositories.quotes import SQLiteQuoteRepository
from sisyphus.schemas import QuoteCategory


def _database(path: Path, *, schema_version: int = 2) -> Path:
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
                category text not null,
                work text,
                source_name text not null,
                source_license text not null,
                source_url text not null,
                character_count integer not null,
                is_daily_eligible integer not null
            );"""
        )
        connection.execute(
            """insert into build_metadata values (
                   ?, '0123456789abcdef', '2026-07-13T12:00:00Z',
                   '2', '1', 'run-test', ?, 'commit-test'
               )""",
            [schema_version, "a" * 64],
        )
        connection.executemany(
            "insert into thinkers values (?, ?)",
            [("Q34670", "Albert Camus"), ("Q9358", "Friedrich Nietzsche")],
        )
        connection.executemany(
            "insert into quotes values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "occ-1",
                    "Q34670",
                    "A liberdade é uma oportunidade de ser melhor.",
                    "verificada",
                    None,
                    "Wikiquote",
                    "CC BY-SA 4.0",
                    "https://example.test/camus",
                    48,
                    1,
                ),
                (
                    "occ-2",
                    "Q34670",
                    "Criar é viver duas vezes, com atenção ao mundo.",
                    "obra",
                    "O Mito de Sísifo",
                    "Wikiquote",
                    "CC BY-SA 4.0",
                    "https://example.test/camus",
                    49,
                    1,
                ),
                (
                    "occ-3",
                    "Q9358",
                    "Este registro não pode participar da seleção diária.",
                    "verificada",
                    None,
                    "Wikiquote",
                    "CC BY-SA 4.0",
                    "https://example.test/nietzsche",
                    54,
                    0,
                ),
            ],
        )
    return path


def test_daily_selection_is_stable_and_reports_dataset(tmp_path: Path) -> None:
    repository = SQLiteQuoteRepository(_database(tmp_path / "sisyphus.db"))

    first = repository.select(thinker="Albert Camus", on_date=date(2026, 7, 13))
    second = repository.select(thinker="Albert Camus", on_date=date(2026, 7, 13))

    assert first == second
    assert first.data == "2026-07-13"
    assert first.dataset_version == "0123456789abcdef"
    assert first.dataset_schema == 2
    assert first.frase.fonte.licenca == "CC BY-SA 4.0"


def test_daily_selection_applies_curated_filters(tmp_path: Path) -> None:
    repository = SQLiteQuoteRepository(_database(tmp_path / "sisyphus.db"))

    result = repository.select(
        thinker="Albert Camus",
        category=QuoteCategory.obra,
        max_length=60,
        on_date=date(2026, 7, 13),
    )

    assert result.frase.categoria is QuoteCategory.obra
    assert result.frase.obra == "O Mito de Sísifo"


def test_ineligible_quote_never_participates(tmp_path: Path) -> None:
    repository = SQLiteQuoteRepository(_database(tmp_path / "sisyphus.db"))

    with pytest.raises(NoQuotesAvailable):
        repository.select(thinker="Friedrich Nietzsche", on_date=date(2026, 7, 13))


def test_collection_membership_is_validated(tmp_path: Path) -> None:
    repository = SQLiteQuoteRepository(_database(tmp_path / "sisyphus.db"))

    with pytest.raises(InvalidSelection):
        repository.select(
            thinker="Albert Camus",
            collection_slug="ciencia-e-curiosidade",
            on_date=date(2026, 7, 13),
        )


def test_unknown_thinker_is_rejected_before_query(tmp_path: Path) -> None:
    repository = SQLiteQuoteRepository(_database(tmp_path / "sisyphus.db"))

    with pytest.raises(ThinkerNotFound, match="não pertence ao catálogo"):
        repository.select(thinker="Pessoa desconhecida", on_date=date(2026, 7, 13))


def test_missing_database_fails_without_fallback(tmp_path: Path) -> None:
    repository = SQLiteQuoteRepository(tmp_path / "missing.db")

    with pytest.raises(DatasetUnavailable, match="ausente ou ilegível"):
        repository.select(on_date=date(2026, 7, 13))


def test_incompatible_database_fails_without_fallback(tmp_path: Path) -> None:
    repository = SQLiteQuoteRepository(_database(tmp_path / "incompatible.db", schema_version=999))

    with pytest.raises(DatasetUnavailable, match="Versão incompatível"):
        repository.select(on_date=date(2026, 7, 13))


def test_invalid_provenance_fails_without_fallback(tmp_path: Path) -> None:
    path = _database(tmp_path / "invalid-provenance.db")
    with sqlite3.connect(path) as connection:
        connection.execute("update build_metadata set manifest_sha256 = 'invalid'")

    with pytest.raises(DatasetUnavailable, match="Hash do manifesto"):
        SQLiteQuoteRepository(path).select(on_date=date(2026, 7, 13))


@respx.mock
def test_readiness_reports_dataset_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "serving_db_path", _database(tmp_path / "sisyphus.db"))
    respx.get(settings.wikiquote_api).mock(return_value=httpx.Response(200))
    respx.get(settings.wikidata_api).mock(return_value=httpx.Response(200))

    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["dataset"] == {
        "status": "ok",
        "schema": 2,
        "version": "0123456789abcdef",
    }


def test_local_dataset_health_does_not_call_upstreams(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "serving_db_path", _database(tmp_path / "sisyphus.db"))

    with TestClient(create_app()) as client:
        response = client.get("/health/dataset")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dataset": {"status": "ok", "schema": 2, "version": "0123456789abcdef"},
    }


def test_local_dataset_health_fails_without_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "serving_db_path", tmp_path / "missing.db")

    with TestClient(create_app()) as client:
        response = client.get("/health/dataset")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "dataset": {"status": "down"}}


@respx.mock
def test_readiness_is_degraded_without_dataset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "serving_db_path", tmp_path / "missing.db")
    respx.get(settings.wikiquote_api).mock(return_value=httpx.Response(200))
    respx.get(settings.wikidata_api).mock(return_value=httpx.Response(200))

    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dataset"] == {"status": "down"}
