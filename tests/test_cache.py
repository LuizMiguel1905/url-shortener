import time

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cache, redirects, services
from app.cache import redis_client
from app.config import settings
from app.models import Link

TARGET = "https://example.com/page"
CODE = "cached1"


def create(client: TestClient) -> None:
    response = client.post("/links", json={"url": TARGET, "custom_code": CODE})
    assert response.status_code == 201


def follow(client: TestClient, code: str = CODE) -> int:
    return client.get(f"/{code}", follow_redirects=False).status_code


def clicks_in_database(db: Session) -> int | None:
    return db.scalar(select(Link.clicks).where(Link.code == CODE))


class TestCacheAside:
    def test_create_warms_the_cache_with_a_ttl(self, client: TestClient) -> None:
        create(client)

        assert redis_client.get(f"link:{CODE}") == TARGET
        assert 0 < redis_client.ttl(f"link:{CODE}") <= settings.cache_ttl_seconds

    def test_miss_loads_from_database_and_caches(self, client: TestClient, db: Session) -> None:
        services.create_link(db, TARGET, CODE)
        assert redis_client.get(f"link:{CODE}") is None

        assert follow(client) == 307

        assert redis_client.get(f"link:{CODE}") == TARGET

    def test_hit_does_not_query_the_database(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create(client)

        def database_must_not_be_used(*args: object, **kwargs: object) -> None:
            raise AssertionError("O banco foi consultado em um cache hit")

        monkeypatch.setattr(services, "find_target_url", database_must_not_be_used)

        assert follow(client) == 307

    def test_expired_entry_is_reloaded_from_database(self, client: TestClient) -> None:
        create(client)
        redis_client.pexpire(f"link:{CODE}", 20)
        time.sleep(0.1)
        assert redis_client.get(f"link:{CODE}") is None

        assert follow(client) == 307

        assert redis_client.get(f"link:{CODE}") == TARGET

    def test_unknown_code_is_not_cached(self, client: TestClient) -> None:
        assert follow(client, "nope") == 404

        assert redis_client.exists("link:nope") == 0
        assert redis_client.exists("clicks:nope") == 0


class TestPendingClicks:
    def test_clicks_stay_in_redis_until_flushed(self, client: TestClient, db: Session) -> None:
        create(client)
        for _ in range(3):
            follow(client)

        assert clicks_in_database(db) == 0
        assert redis_client.get(f"clicks:{CODE}") == "3"

        assert redirects.flush_pending_clicks() == 3

        assert clicks_in_database(db) == 3
        assert redis_client.get(f"clicks:{CODE}") is None
        assert redis_client.scard(cache.DIRTY_CODES_KEY) == 0

    def test_failed_flush_keeps_the_clicks(
        self, client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create(client)
        follow(client)
        follow(client)

        def database_is_down(clicks_by_code: dict[str, int]) -> None:
            raise RuntimeError("banco indisponível")

        monkeypatch.setattr(redirects, "_add_clicks_in_database", database_is_down)
        with pytest.raises(RuntimeError):
            redirects.flush_pending_clicks()
        monkeypatch.undo()

        assert redis_client.get(f"clicks:{CODE}") == "2"
        assert redis_client.sismember(cache.DIRTY_CODES_KEY, CODE)
        assert redirects.flush_pending_clicks() == 2
        assert clicks_in_database(db) == 2


class TestRedisUnavailable:
    @pytest.fixture
    def unreachable_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        broken = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1, decode_responses=True)
        monkeypatch.setattr(cache, "redis_client", broken)

    @pytest.mark.usefixtures("unreachable_redis")
    def test_requests_fall_back_to_the_database(self, client: TestClient, db: Session) -> None:
        create(client)

        assert follow(client) == 307
        assert follow(client) == 307

        assert clicks_in_database(db) == 2
