from fastapi import FastAPI
from fastapi.testclient import TestClient

from sisyphus.middleware import RequestIdMiddleware
from sisyphus.ratelimit import RateLimitMiddleware


def test_rate_limit_returns_problem_details_and_retry_header() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=2, window=60)

    @app.get("/resource")
    async def resource() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/resource").status_code == 200
    assert client.get("/resource").status_code == 200
    limited = client.get("/resource")

    assert limited.status_code == 429
    assert limited.headers["content-type"].startswith("application/problem+json")
    assert "retry-after" in limited.headers
    assert limited.json()["type"] == "/problems/rate-limited"


def test_request_id_is_preserved() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/resource")
    async def resource() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/resource", headers={"X-Request-ID": "trace-123"})

    assert response.headers["X-Request-ID"] == "trace-123"


def test_invalid_request_id_is_replaced() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/resource")
    async def resource() -> dict[str, bool]:
        return {"ok": True}

    supplied = "x" * 500
    response = TestClient(app).get("/resource", headers={"X-Request-ID": supplied})

    assert response.headers["X-Request-ID"] != supplied
    assert len(response.headers["X-Request-ID"]) == 32
