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


async def _dataset_status() -> tuple[dict[str, str | int], bool]:
    repository = SQLiteQuoteRepository(settings.serving_db_path)
    try:
        metadata = await asyncio.to_thread(repository.metadata)
        return (
            {
                "status": "ok",
                "schema": metadata.schema_version,
                "version": metadata.dataset_version,
            },
            True,
        )
    except DatasetUnavailable:
        return {"status": "down"}, False


@router.get(
    "/health/dataset",
    summary="Healthcheck local — o artefato curado está pronto",
)
async def dataset_health() -> JSONResponse:
    dataset, ok = await _dataset_status()
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "degraded", "dataset": dataset},
    )


@router.get("/health/ready", summary="Readiness — as fontes upstream respondem")
async def ready(request: Request) -> JSONResponse:
    http: httpx.AsyncClient = request.app.state.http
    wq, wd = await asyncio.gather(
        _ping(http, settings.wikiquote_api),
        _ping(http, settings.wikidata_api),
    )
    sources = {"wikiquote": wq, "wikidata": wd}
    dataset, dataset_ok = await _dataset_status()
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
