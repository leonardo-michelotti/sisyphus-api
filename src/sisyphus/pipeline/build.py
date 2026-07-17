from __future__ import annotations

import asyncio
import csv
import hashlib
import html
import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import httpx

from sisyphus.catalog import ALL_THINKERS, DAILY_QUOTES_PER_THINKER
from sisyphus.clients.wikiquote import _page_url, parse_quotes
from sisyphus.config import settings
from sisyphus.dataset import SERVING_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
BRONZE = DATA / "bronze"
WAREHOUSE = DATA / "sisyphus.duckdb"
SERVING = DATA / "sisyphus.db"
REPORT = ROOT / "reports" / "data-quality.html"
PARSER_VERSION = "1"
PIPELINE_VERSION = "3"
MAX_FETCH_ATTEMPTS = 3
MAX_CONCURRENT_FETCHES = 4
TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
SUPPLEMENTAL_QUOTES = ROOT / "editorial" / "supplemental_quotes.csv"
SUPPLEMENTAL_FIELDS = (
    "thinker_qid",
    "thinker_name",
    "text",
    "original_text",
    "original_language",
    "category",
    "work",
    "source_url",
    "source_name",
    "source_license",
    "source_revision",
    "translator_name",
    "translation_license",
    "translation_url",
    "reviewed_at",
)


@dataclass(frozen=True)
class Snapshot:
    name: str
    title: str
    qid: str
    revision: int
    fetched_at: str
    wikiquote: dict[str, Any]
    wikidata: dict[str, Any]


def _retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
    if response is not None and (retry_after := response.headers.get("Retry-After")):
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            pass
    jitter = int.from_bytes(os.urandom(2), "big") / 655_350
    return 0.25 * (1 << attempt) + jitter


async def _get_with_retry(
    client: httpx.AsyncClient, url: str, *, params: dict[str, Any]
) -> httpx.Response:
    last_error: httpx.HTTPError | None = None
    for attempt in range(MAX_FETCH_ATTEMPTS):
        response: httpx.Response | None = None
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in TRANSIENT_STATUS_CODES:
                raise
            response = exc.response
            last_error = exc
        except (httpx.NetworkError, httpx.TimeoutException) as exc:
            last_error = exc
        if attempt == MAX_FETCH_ATTEMPTS - 1:
            assert last_error is not None
            raise last_error
        await asyncio.sleep(_retry_delay(attempt, response))
    raise AssertionError("tentativas HTTP encerradas sem resultado")


async def _fetch_one(client: httpx.AsyncClient, name: str) -> Snapshot:
    resolved = await _get_with_retry(
        client,
        settings.wikiquote_api,
        params={
            "action": "query",
            "titles": name,
            "prop": "pageprops",
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        },
    )
    page = resolved.json()["query"]["pages"][0]
    qid = page.get("pageprops", {}).get("wikibase_item")
    if not qid:
        raise RuntimeError(f"{name}: página sem QID")
    title = page["title"]
    wikiquote_response = await _get_with_retry(
        client,
        settings.wikiquote_api,
        params={
            "action": "parse",
            "page": title,
            "prop": "text|revid",
            "format": "json",
            "formatversion": 2,
        },
    )
    wikidata_response = await _get_with_retry(
        client,
        settings.wikidata_api,
        params={
            "action": "wbgetentities",
            "ids": qid,
            "props": "labels|descriptions|claims",
            "languages": "pt|en",
            "format": "json",
            "formatversion": 2,
        },
    )
    wikiquote = wikiquote_response.json()
    parsed = wikiquote.get("parse") if isinstance(wikiquote, dict) else None
    revision = parsed.get("revid") if isinstance(parsed, dict) else None
    if not isinstance(revision, int):
        raise RuntimeError(f"{name}: resposta sem revisão do conteúdo interpretado")
    return Snapshot(
        name=name,
        title=title,
        qid=qid,
        revision=revision,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        wikiquote=wikiquote,
        wikidata=wikidata_response.json(),
    )


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _source_record(item: Snapshot, run_dir: Path) -> dict[str, Any]:
    wikiquote_bytes = _json_bytes(item.wikiquote)
    wikidata_bytes = _json_bytes(item.wikidata)
    wikiquote_hash = hashlib.sha256(wikiquote_bytes).hexdigest()
    wikidata_hash = hashlib.sha256(wikidata_bytes).hexdigest()
    wikiquote_path = run_dir / "wikiquote" / f"{item.qid}-{item.revision}-{wikiquote_hash}.json"
    wikidata_path = run_dir / "wikidata" / f"{item.qid}-{wikidata_hash}.json"
    wikiquote_path.parent.mkdir(parents=True, exist_ok=True)
    wikidata_path.parent.mkdir(parents=True, exist_ok=True)
    wikiquote_path.write_bytes(wikiquote_bytes)
    wikidata_path.write_bytes(wikidata_bytes)
    return {
        "requested_name": item.name,
        "wikiquote_title": item.title,
        "qid": item.qid,
        "wikiquote_revision": item.revision,
        "wikiquote_file": wikiquote_path.relative_to(run_dir).as_posix(),
        "wikiquote_sha256": wikiquote_hash,
        "wikidata_file": wikidata_path.relative_to(run_dir).as_posix(),
        "wikidata_sha256": wikidata_hash,
        "fetched_at": item.fetched_at,
        "status": "success",
    }


def _write_manifest(
    run_dir: Path,
    *,
    run_id: str,
    status: str,
    sources: list[dict[str, Any]],
    error: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "parser_version": PARSER_VERSION,
        "sources": sources,
    }
    if error:
        payload["error"] = error
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    (run_dir / "manifest.json").write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _record_build_provenance(
    warehouse: Path,
    *,
    run_id: str,
    manifest_sha256: str,
) -> None:
    if len(manifest_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in manifest_sha256
    ):
        raise ValueError("manifest_sha256 deve ser um SHA-256 hexadecimal")
    source_commit = os.environ.get("SISYPHUS_SOURCE_COMMIT", "local").strip() or "local"
    with duckdb.connect(str(warehouse)) as connection:
        connection.execute("drop table if exists pipeline_build_metadata")
        connection.execute(
            """create table pipeline_build_metadata as select
               ?::varchar run_id,
               ?::varchar manifest_sha256,
               ?::varchar pipeline_version,
               ?::varchar parser_version,
               ?::varchar source_commit""",
            [run_id, manifest_sha256, PIPELINE_VERSION, PARSER_VERSION, source_commit],
        )


async def ingest(
    *,
    bronze_root: Path = BRONZE,
    warehouse: Path = WAREHOUSE,
    run_id: str | None = None,
    concurrency: int = MAX_CONCURRENT_FETCHES,
) -> list[Snapshot]:
    """Baixa um snapshot identificável das fontes e atualiza as tabelas bronze."""
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if concurrency < 1:
        raise ValueError("concurrency deve ser maior que zero")
    run_dir = bronze_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    headers = {"User-Agent": settings.user_agent}
    sources: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(headers=headers, timeout=settings.http_timeout) as client:
            semaphore = asyncio.Semaphore(concurrency)

            async def fetch_limited(name: str) -> Snapshot:
                async with semaphore:
                    return await _fetch_one(client, name)

            results = await asyncio.gather(
                *(fetch_limited(name) for name in ALL_THINKERS), return_exceptions=True
            )
        snapshots: list[Snapshot] = []
        for name, result in zip(ALL_THINKERS, results, strict=True):
            if isinstance(result, BaseException):
                sources.append(
                    {
                        "requested_name": name,
                        "status": "failed",
                        "error": type(result).__name__,
                    }
                )
            else:
                snapshots.append(result)
                sources.append(_source_record(result, run_dir))
        if len(snapshots) != len(ALL_THINKERS):
            raise RuntimeError("uma ou mais fontes falharam; o warehouse não foi atualizado")
        _load_bronze(snapshots, warehouse=warehouse, bronze_dir=run_dir)
        manifest_sha256 = _write_manifest(
            run_dir, run_id=run_id, status="complete", sources=sources
        )
        _record_build_provenance(
            warehouse,
            run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
    except Exception as exc:
        _write_manifest(
            run_dir, run_id=run_id, status="failed", sources=sources, error=type(exc).__name__
        )
        raise
    return list(snapshots)


def _read_supplemental_quotes(path: Path) -> list[tuple[object, ...]]:
    """Lê a fonte editorial versionada e bloqueia proveniência incompleta."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != SUPPLEMENTAL_FIELDS:
            raise ValueError("cabeçalho da fonte suplementar é incompatível")
        records = list(reader)

    rows: list[tuple[object, ...]] = []
    seen: set[tuple[str, str]] = set()
    for line_number, raw in enumerate(records, start=2):
        record = {field: (raw.get(field) or "").strip() for field in SUPPLEMENTAL_FIELDS}
        required = (
            "thinker_qid",
            "thinker_name",
            "text",
            "category",
            "source_url",
            "source_name",
            "source_license",
            "source_revision",
            "reviewed_at",
        )
        missing = [field for field in required if not record[field]]
        if missing:
            raise ValueError(
                f"fonte suplementar, linha {line_number}: campos ausentes: {', '.join(missing)}"
            )
        if record["thinker_name"] not in ALL_THINKERS:
            raise ValueError(f"fonte suplementar, linha {line_number}: pensador fora do catálogo")
        if record["category"] not in {"verificada", "obra", "atribuida"}:
            raise ValueError(f"fonte suplementar, linha {line_number}: categoria inválida")
        if not record["source_url"].startswith("https://"):
            raise ValueError(f"fonte suplementar, linha {line_number}: source_url deve usar HTTPS")
        try:
            source_revision = int(record["source_revision"])
        except ValueError as exc:
            raise ValueError(
                f"fonte suplementar, linha {line_number}: source_revision deve ser inteiro"
            ) from exc
        if source_revision < 1:
            raise ValueError(
                f"fonte suplementar, linha {line_number}: source_revision deve ser positivo"
            )
        try:
            reviewed_at = datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"fonte suplementar, linha {line_number}: reviewed_at deve ser ISO 8601"
            ) from exc
        if reviewed_at.tzinfo is None:
            raise ValueError(
                f"fonte suplementar, linha {line_number}: reviewed_at deve conter fuso horário"
            )

        translation_fields = (
            record["original_language"],
            record["translator_name"],
            record["translation_license"],
            record["translation_url"],
        )
        if record["original_text"] and not all(translation_fields):
            raise ValueError(
                f"fonte suplementar, linha {line_number}: tradução sem proveniência completa"
            )
        if not record["original_text"] and any(translation_fields):
            raise ValueError(
                f"fonte suplementar, linha {line_number}: metadados de tradução sem original"
            )
        if record["translation_url"] and not record["translation_url"].startswith("https://"):
            raise ValueError(
                f"fonte suplementar, linha {line_number}: translation_url deve usar HTTPS"
            )
        identity = (record["thinker_qid"], record["text"])
        if identity in seen:
            raise ValueError(f"fonte suplementar, linha {line_number}: frase duplicada")
        seen.add(identity)
        rows.append(
            (
                record["thinker_qid"],
                record["thinker_name"],
                record["text"],
                record["original_text"] or None,
                record["original_language"] or None,
                record["category"],
                record["work"] or None,
                record["source_url"],
                record["source_name"],
                record["source_license"],
                source_revision,
                record["translator_name"] or None,
                record["translation_license"] or None,
                record["translation_url"] or None,
                reviewed_at,
            )
        )
    return rows


def _load_bronze(
    snapshots: list[Snapshot],
    *,
    warehouse: Path = WAREHOUSE,
    bronze_dir: Path = BRONZE,
    supplemental_path: Path = SUPPLEMENTAL_QUOTES,
) -> None:
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    bronze_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(warehouse)) as con:
        con.execute("drop table if exists bronze_quotes")
        con.execute("drop table if exists bronze_supplemental_quotes")
        con.execute("drop table if exists bronze_thinkers")
        con.execute(
            """create table bronze_quotes (
                thinker_qid varchar, thinker_name varchar, text varchar, category varchar,
                work varchar, source_url varchar, source_name varchar, source_license varchar,
                source_revision bigint, fetched_at timestamptz
            )"""
        )
        con.execute(
            """create table bronze_supplemental_quotes (
                thinker_qid varchar, thinker_name varchar, text varchar,
                original_text varchar, original_language varchar, category varchar,
                work varchar, source_url varchar, source_name varchar, source_license varchar,
                source_revision bigint, translator_name varchar, translation_license varchar,
                translation_url varchar, reviewed_at timestamptz
            )"""
        )
        supplemental_rows = _read_supplemental_quotes(supplemental_path)
        if supplemental_rows:
            con.executemany(
                "insert into bronze_supplemental_quotes values "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                supplemental_rows,
            )
        con.execute(
            """create table bronze_thinkers (
                qid varchar, name varchar, wikiquote_title varchar, source_url varchar,
                source_revision bigint, fetched_at timestamptz
            )"""
        )
        for item in snapshots:
            parsed = item.wikiquote.get("parse", {})
            page_html = parsed.get("text", "")
            quotes = parse_quotes(page_html, item.title, _page_url(item.title))
            con.execute(
                "insert into bronze_thinkers values (?, ?, ?, ?, ?, ?)",
                [
                    item.qid,
                    item.name,
                    item.title,
                    _page_url(item.title),
                    item.revision,
                    item.fetched_at,
                ],
            )
            rows = [
                [
                    item.qid,
                    item.name,
                    quote.texto,
                    quote.categoria.value,
                    quote.obra,
                    quote.fonte.url,
                    quote.fonte.fonte,
                    quote.fonte.licenca,
                    item.revision,
                    item.fetched_at,
                ]
                for quote in quotes
            ]
            if rows:
                con.executemany(
                    "insert into bronze_quotes values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
                )
        con.execute(
            f"copy bronze_quotes to '{(bronze_dir / 'quotes.parquet').as_posix()}' "
            "(format parquet, compression zstd)"
        )
        con.execute(
            "copy bronze_supplemental_quotes to "
            f"'{(bronze_dir / 'supplemental_quotes.parquet').as_posix()}' "
            "(format parquet, compression zstd)"
        )
        con.execute(
            f"copy bronze_thinkers to '{(bronze_dir / 'thinkers.parquet').as_posix()}' "
            "(format parquet, compression zstd)"
        )
        con.execute("drop table if exists pipeline_build_metadata")


def transform(
    *,
    warehouse: Path = WAREHOUSE,
    daily_quotes_per_thinker: int = DAILY_QUOTES_PER_THINKER,
    validate_editorial_queue: bool = True,
) -> None:
    executable = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
    env = {**os.environ, "SISYPHUS_WAREHOUSE_PATH": str(warehouse.resolve())}
    subprocess.run(
        [
            str(executable),
            "build",
            "--project-dir",
            ".",
            "--profiles-dir",
            ".",
            "--vars",
            json.dumps(
                {
                    "daily_quotes_per_thinker": daily_quotes_per_thinker,
                    "validate_editorial_queue": validate_editorial_queue,
                }
            ),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


def _dataset_version(
    thinkers: list[tuple[Any, ...]],
    quotes: list[tuple[Any, ...]],
) -> str:
    digest = hashlib.sha256(f"schema:{SERVING_SCHEMA_VERSION}\n".encode())
    for label, rows in (("thinker", thinkers), ("quote", quotes)):
        for row in rows:
            payload = json.dumps(
                [label, *row],
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
            digest.update(payload.encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()[:16]


def publish(
    *,
    warehouse: Path = WAREHOUSE,
    serving: Path = SERVING,
    expected_thinkers: Collection[str] = ALL_THINKERS,
    daily_quotes_per_thinker: int = DAILY_QUOTES_PER_THINKER,
) -> None:
    """Gera e valida um SQLite novo antes de substituir o artefato publicado."""
    serving.parent.mkdir(parents=True, exist_ok=True)
    candidate = serving.with_name(f".{serving.name}.next")
    candidate.unlink(missing_ok=True)
    try:
        out = sqlite3.connect(candidate)
        try:
            out.execute("pragma foreign_keys = on")
            with duckdb.connect(str(warehouse), read_only=True) as source:
                available_thinkers = {
                    row[0]
                    for row in source.execute("select thinker_name from dim_thinkers").fetchall()
                }
                missing_thinkers = set(expected_thinkers) - available_thinkers
                if missing_thinkers:
                    names = ", ".join(sorted(missing_thinkers))
                    raise RuntimeError(f"publicação bloqueada: pensadores ausentes: {names}")
                eligible = source.execute(
                    "select count(*) from fct_quotes where is_daily_eligible"
                ).fetchone()
                if eligible is None or eligible[0] < 1:
                    raise RuntimeError("publicação bloqueada: nenhuma frase elegível")
                eligible_thinkers = {
                    row[0]
                    for row in source.execute(
                        """select distinct thinkers.thinker_name
                           from fct_quotes as quotes
                           join dim_thinkers as thinkers
                             on thinkers.thinker_qid = quotes.thinker_qid
                           where quotes.is_daily_eligible"""
                    ).fetchall()
                }
                without_daily_quote = set(expected_thinkers) - eligible_thinkers
                if without_daily_quote:
                    names = ", ".join(sorted(without_daily_quote))
                    raise RuntimeError(
                        f"publicação bloqueada: pensadores sem frase elegível: {names}"
                    )
                invalid_daily_counts = source.execute(
                    """select thinkers.thinker_name, count(*) as quote_count
                       from fct_quotes as quotes
                       join dim_thinkers as thinkers
                         on thinkers.thinker_qid = quotes.thinker_qid
                       where quotes.is_daily_eligible
                       group by thinkers.thinker_name
                       having count(*) != ?
                       order by thinkers.thinker_name""",
                    [daily_quotes_per_thinker],
                ).fetchall()
                if invalid_daily_counts:
                    counts = ", ".join(f"{name} ({count})" for name, count in invalid_daily_counts)
                    raise RuntimeError(
                        "publicação bloqueada: quantidade de frases elegíveis "
                        f"diferente de {daily_quotes_per_thinker}: {counts}"
                    )
                provenance = source.execute(
                    """select run_id, manifest_sha256, pipeline_version,
                              parser_version, source_commit
                       from pipeline_build_metadata"""
                ).fetchone()
                if provenance is None:
                    raise RuntimeError("publicação bloqueada: proveniência da execução ausente")
                out.executescript(
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
                        thinker_name text not null,
                        wikiquote_title text not null,
                        source_url text not null,
                        source_revision integer not null,
                        fetched_at text not null
                    );
                    create table quotes (
                        occurrence_id text primary key,
                        quote_id text not null,
                        thinker_qid text not null references thinkers(thinker_qid),
                        quote_text text not null,
                        original_text text,
                        original_language text,
                        category text not null,
                        work text,
                        source_url text not null,
                        source_name text not null,
                        source_license text not null,
                        source_revision integer not null,
                        translator_name text,
                        translation_license text,
                        translation_url text,
                        character_count integer not null,
                        curation_status text not null,
                        quality_reason text not null,
                        quality_reasons text not null,
                        is_daily_eligible integer not null check (is_daily_eligible in (0, 1))
                    );
                    create virtual table quotes_fts using fts5(
                        quote_text, content=quotes, content_rowid=rowid
                    );
                    """
                )
                thinkers = source.execute(
                    """select thinker_qid, thinker_name, wikiquote_title, source_url,
                              source_revision, cast(fetched_at as varchar)
                       from dim_thinkers order by thinker_name"""
                ).fetchall()
                out.executemany("insert into thinkers values (?, ?, ?, ?, ?, ?)", thinkers)
                quotes = source.execute(
                    """select occurrence_id, quote_id, thinker_qid, quote_text,
                              original_text, original_language, category, work,
                              source_url, source_name, source_license, source_revision,
                              translator_name, translation_license, translation_url,
                              character_count, curation_status, quality_reason,
                              to_json(quality_reasons), cast(is_daily_eligible as integer)
                       from fct_quotes order by thinker_qid, occurrence_id"""
                ).fetchall()
                source_fetched_at = source.execute(
                    "select cast(max(fetched_at) as varchar) from dim_thinkers"
                ).fetchone()
                assert source_fetched_at is not None and source_fetched_at[0] is not None
                fingerprint_thinkers = [tuple(row[:5]) for row in thinkers]
                dataset_version = _dataset_version(fingerprint_thinkers, quotes)
                out.execute(
                    "insert into build_metadata values (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        SERVING_SCHEMA_VERSION,
                        dataset_version,
                        source_fetched_at[0],
                        provenance[2],
                        provenance[3],
                        provenance[0],
                        provenance[1],
                        provenance[4],
                    ],
                )
                out.executemany(
                    "insert into quotes values "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    quotes,
                )
            out.execute(
                "insert into quotes_fts(rowid, quote_text) select rowid, quote_text from quotes"
            )
            out.execute("create index idx_quotes_quote on quotes(quote_id)")
            out.execute("create index idx_quotes_thinker on quotes(thinker_qid)")
            out.execute("create index idx_quotes_daily on quotes(is_daily_eligible)")
            if out.execute("pragma integrity_check").fetchone() != ("ok",):
                raise RuntimeError("falha na verificação de integridade do SQLite")
            if out.execute("select count(*) from quotes").fetchone() != (len(quotes),):
                raise RuntimeError("contagem divergente no SQLite publicado")
            out.execute("select count(*) from quotes_fts where quotes_fts match 'sisyphus'")
            out.commit()
        finally:
            out.close()
        os.replace(candidate, serving)
    except Exception:
        candidate.unlink(missing_ok=True)
        raise


def audit(*, warehouse: Path = WAREHOUSE, report: Path = REPORT) -> dict[str, int]:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        row = con.execute(
            """select count(*) total,
                      count(distinct thinker_qid) thinkers,
                      count(*) filter (where curation_status = 'accepted') accepted,
                      count(*) filter (where curation_status = 'review') review,
                      count(*) filter (where curation_status = 'rejected') rejected,
                      count(*) filter (where is_daily_eligible) daily
               from fct_quotes"""
        ).fetchone()
        assert row is not None
        names = ("total", "thinkers", "accepted", "review", "rejected", "daily")
        metrics = dict(zip(names, row, strict=True))
        reasons = con.execute(
            "select quality_reason, count(*) from fct_quotes group by 1 order by 2 desc"
        ).fetchall()
        suspects = con.execute(
            """select thinker_name, quote_text, quality_reason from fct_quotes
               where curation_status <> 'accepted'
               order by character_count desc limit 20"""
        ).fetchall()

    report.parent.mkdir(parents=True, exist_ok=True)
    cards = "".join(
        f"<article><strong>{value}</strong><span>{label}</span></article>"
        for label, value in metrics.items()
    )
    reason_rows = "".join(
        f"<tr><td>{html.escape(reason)}</td><td>{count}</td></tr>" for reason, count in reasons
    )
    suspect_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{html.escape(text)}</td><td>{reason}</td></tr>"
        for name, text, reason in suspects
    )
    report.write_text(
        f"""<!doctype html><html lang='pt-BR'><meta charset='utf-8'>
<meta name='viewport' content='width=device-width'><title>Auditoria de dados | Sisyphus</title>
<style>
body{{margin:0;background:#11100e;color:#e9e4d8;font:16px/1.55 Georgia,serif}}
main{{max-width:1080px;margin:auto;padding:64px 24px}}
h1{{font-size:clamp(2.4rem,7vw,5rem);line-height:.95;margin:.2em 0}}
p{{max-width:720px;color:#bdb6a8}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
gap:1px;background:#3b3730;margin:40px 0}}
article{{background:#181613;padding:24px}}
strong{{display:block;font:2rem Arial,sans-serif;color:#d3a750}}
span{{color:#aaa296}}
table{{border-collapse:collapse;width:100%;margin:20px 0 48px}}
th,td{{border-bottom:1px solid #39352f;padding:12px;text-align:left;vertical-align:top}}
th{{font:12px Arial,sans-serif;text-transform:uppercase;color:#d3a750}}
td:nth-child(2){{max-width:650px}}small{{color:#8f887d}}
</style>
<main><small>SISYPHUS / CONTROLE EDITORIAL</small><h1>A base antes da frase.</h1>
<p>Este relatório separa conteúdo coletado de conteúdo pronto para o produto e
torna cada exclusão explicável.</p>
<section class='cards'>{cards}</section><h2>Resultado das regras</h2>
<table><thead><tr><th>Motivo</th><th>Registros</th></tr></thead>
<tbody>{reason_rows}</tbody></table>
<h2>Amostra para revisão humana</h2>
<table><thead><tr><th>Autor</th><th>Texto</th><th>Motivo</th></tr></thead>
<tbody>{suspect_rows}</tbody></table></main></html>""",
        encoding="utf-8",
    )
    return metrics


def run() -> dict[str, int]:
    asyncio.run(ingest())
    transform()
    publish()
    return audit()
