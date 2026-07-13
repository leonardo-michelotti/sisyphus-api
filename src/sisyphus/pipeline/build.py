from __future__ import annotations

import asyncio
import html
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import httpx

from sisyphus.catalog import ALL_THINKERS
from sisyphus.clients.wikiquote import _page_url, parse_quotes
from sisyphus.config import settings

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
BRONZE = DATA / "bronze"
WAREHOUSE = DATA / "sisyphus.duckdb"
SERVING = DATA / "sisyphus.db"
REPORT = ROOT / "reports" / "data-quality.html"


@dataclass(frozen=True)
class Snapshot:
    name: str
    title: str
    qid: str
    revision: int
    fetched_at: str
    wikiquote: dict[str, Any]
    wikidata: dict[str, Any]


async def _fetch_one(client: httpx.AsyncClient, name: str) -> Snapshot:
    resolved = await client.get(
        settings.wikiquote_api,
        params={
            "action": "query",
            "titles": name,
            "prop": "pageprops|info",
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        },
    )
    resolved.raise_for_status()
    page = resolved.json()["query"]["pages"][0]
    qid = page.get("pageprops", {}).get("wikibase_item")
    if not qid:
        raise RuntimeError(f"{name}: página sem QID")
    title = page["title"]
    revision = int(page["lastrevid"])

    wikiquote_response, wikidata_response = await asyncio.gather(
        client.get(
            settings.wikiquote_api,
            params={
                "action": "parse",
                "page": title,
                "prop": "text|revid",
                "format": "json",
                "formatversion": 2,
            },
        ),
        client.get(
            settings.wikidata_api,
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "labels|descriptions|claims",
                "languages": "pt|en",
                "format": "json",
                "formatversion": 2,
            },
        ),
    )
    wikiquote_response.raise_for_status()
    wikidata_response.raise_for_status()
    return Snapshot(
        name=name,
        title=title,
        qid=qid,
        revision=revision,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        wikiquote=wikiquote_response.json(),
        wikidata=wikidata_response.json(),
    )


async def ingest() -> list[Snapshot]:
    """Baixa um snapshot identificável das fontes e atualiza as tabelas bronze."""
    BRONZE.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=settings.http_timeout) as client:
        snapshots = await asyncio.gather(*(_fetch_one(client, name) for name in ALL_THINKERS))

    for item in snapshots:
        path = BRONZE / f"{item.qid}-{item.revision}.json"
        payload = {
            "metadata": {
                "requested_name": item.name,
                "wikiquote_title": item.title,
                "qid": item.qid,
                "source_revision": item.revision,
                "fetched_at": item.fetched_at,
            },
            "wikiquote": item.wikiquote,
            "wikidata": item.wikidata,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    _load_bronze(snapshots)
    return list(snapshots)


def _load_bronze(
    snapshots: list[Snapshot],
    *,
    warehouse: Path = WAREHOUSE,
    bronze_dir: Path = BRONZE,
) -> None:
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    bronze_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(warehouse)) as con:
        con.execute("drop table if exists bronze_quotes")
        con.execute("drop table if exists bronze_thinkers")
        con.execute(
            """create table bronze_quotes (
                thinker_qid varchar, thinker_name varchar, text varchar, category varchar,
                work varchar, source_url varchar, source_revision bigint, fetched_at timestamptz
            )"""
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
            con.executemany(
                "insert into bronze_quotes values (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    [
                        item.qid,
                        item.name,
                        quote.texto,
                        quote.categoria.value,
                        quote.obra,
                        quote.fonte.url,
                        item.revision,
                        item.fetched_at,
                    ]
                    for quote in quotes
                ],
            )
        con.execute(
            f"copy bronze_quotes to '{(bronze_dir / 'quotes.parquet').as_posix()}' "
            "(format parquet, compression zstd)"
        )
        con.execute(
            f"copy bronze_thinkers to '{(bronze_dir / 'thinkers.parquet').as_posix()}' "
            "(format parquet, compression zstd)"
        )


def transform(*, warehouse: Path = WAREHOUSE) -> None:
    executable = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
    env = {**os.environ, "SISYPHUS_WAREHOUSE_PATH": str(warehouse.resolve())}
    subprocess.run(
        [str(executable), "build", "--project-dir", ".", "--profiles-dir", "."],
        cwd=ROOT,
        env=env,
        check=True,
    )


def publish(*, warehouse: Path = WAREHOUSE, serving: Path = SERVING) -> None:
    """Gera um SQLite descartável e otimizado para leitura pela aplicação."""
    serving.parent.mkdir(parents=True, exist_ok=True)
    serving.unlink(missing_ok=True)
    with duckdb.connect(str(warehouse), read_only=True) as source, sqlite3.connect(serving) as out:
        out.executescript(
            """create table thinkers (
                thinker_qid text primary key,
                thinker_name text not null,
                wikiquote_title text not null,
                source_url text not null, source_revision integer not null, fetched_at text not null
            );
            create table quotes (
                quote_id text primary key,
                thinker_qid text not null references thinkers(thinker_qid),
                quote_text text not null,
                category text not null,
                work text,
                source_url text not null,
                source_revision integer not null, character_count integer not null,
                curation_status text not null, quality_reason text not null,
                is_daily_eligible integer not null
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
            """select quote_id, thinker_qid, quote_text, category, work, source_url,
                      source_revision, character_count, curation_status, quality_reason,
                      cast(is_daily_eligible as integer)
               from fct_quotes order by thinker_qid, quote_id"""
        ).fetchall()
        out.executemany("insert into quotes values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", quotes)
        out.execute(
            "insert into quotes_fts(rowid, quote_text) select rowid, quote_text from quotes"
        )
        out.execute("create index idx_quotes_thinker on quotes(thinker_qid)")
        out.execute("create index idx_quotes_daily on quotes(is_daily_eligible)")


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
