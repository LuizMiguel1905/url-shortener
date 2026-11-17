import asyncio
from collections.abc import Iterator

import anyio.to_thread
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.database import SessionLocal, engine
from app.main import app

POOL_SIZE = 2
THREAD_LIMIT = 4
CONCURRENT_REQUESTS = 40


def _terminate_abandoned_transactions() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                "AND state = 'idle in transaction'"
            )
        )


@pytest.fixture
def small_pool() -> Iterator[None]:
    constrained = create_engine(
        engine.url, pool_size=POOL_SIZE, max_overflow=0, pool_timeout=2, pool_pre_ping=True
    )
    SessionLocal.configure(bind=constrained)
    yield
    SessionLocal.configure(bind=engine)
    _terminate_abandoned_transactions()
    constrained.dispose()


async def send_concurrently(requests: list[tuple[str, str, dict | None]]) -> list[int]:
    anyio.to_thread.current_default_thread_limiter().total_tokens = THREAD_LIMIT
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test.local") as http:
        responses = await asyncio.gather(
            *(
                http.request(method, path, json=payload, follow_redirects=False)
                for method, path, payload in requests
            )
        )
    return [response.status_code for response in responses]


@pytest.mark.usefixtures("small_pool")
def test_create_link_survives_more_requests_than_threads_and_connections() -> None:
    payload = {"url": "https://example.com/page"}
    requests = [("POST", "/links", payload)] * CONCURRENT_REQUESTS

    statuses = asyncio.run(send_concurrently(requests))

    assert statuses == [201] * CONCURRENT_REQUESTS


@pytest.mark.usefixtures("small_pool")
def test_every_route_returns_its_connection_to_the_pool(client: TestClient) -> None:
    pool = SessionLocal.kw["bind"].pool
    client.post("/links", json={"url": "https://example.com/page", "custom_code": "poolcheck"})

    client.post("/links", json={"url": "https://example.com/other", "custom_code": "poolcheck"})
    client.post("/links", json={"url": "not-a-url"})
    client.get("/poolcheck", follow_redirects=False)
    client.get("/doesnotexist", follow_redirects=False)

    assert pool.checkedout() == 0
