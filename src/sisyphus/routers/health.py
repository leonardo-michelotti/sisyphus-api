"""Healthcheck: liveness barato (`/health`) e readiness que checa as fontes."""

from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import __version__
from ..config import settings
from ..errors import DatasetUnavailable
from ..repositories.quotes import SQLiteQuoteRepository

router = APIRouter(tags=["infra"])


@router.get("/health", summary="Liveness — o processo está de pé")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


async def _ping(http: httpx.AsyncClient, url: str) -> bool:
    """Toque leve na API MediaWiki (siteinfo) com timeout curto."""
    try:
        resp = await http.get(
            url,
            params={"action": "query", "meta": "siteinfo", "format": "json"},
            timeout=3.0,
        )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/health/ready", summary="Readiness — as fontes upstream respondem")
async def ready(request: Request) -> JSONResponse:
    http: httpx.AsyncClient = request.app.state.http
    wq, wd = await asyncio.gather(
        _ping(http, settings.wikiquote_api),
        _ping(http, settings.wikidata_api),
    )
    sources = {"wikiquote": wq, "wikidata": wd}
    repository = SQLiteQuoteRepository(settings.serving_db_path)
    try:
        schema_version, dataset_version = await asyncio.to_thread(repository.metadata)
        dataset: dict[str, str | int] = {
            "status": "ok",
            "schema": schema_version,
            "version": dataset_version,
        }
        dataset_ok = True
    except DatasetUnavailable:
        dataset = {"status": "down"}
        dataset_ok = False
    ok = all(sources.values()) and dataset_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "degraded",
            "version": __version__,
            "sources": {k: "ok" if v else "down" for k, v in sources.items()},
            "dataset": dataset,
        },
    )
