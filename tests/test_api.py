import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import redirects, services
from app.config import settings
from app.models import Link

TARGET = "https://example.com/page"


def create(client: TestClient, url: str = TARGET, **extra: str) -> Response:
    return client.post("/links", json={"url": url, **extra})


class TestCreateLink:
    def test_random_code(self, client: TestClient) -> None:
        response = create(client)

        assert response.status_code == 201
        body = response.json()
        assert len(body["code"]) == settings.code_length
        assert body["code"].isalnum()
        assert body["short_url"] == f"http://test.local/{body['code']}"
        assert body["target_url"] == TARGET
        assert body["clicks"] == 0
        assert body["created_at"]

    def test_custom_code(self, client: TestClient) -> None:
        response = create(client, custom_code="my-link_1")

        assert response.status_code == 201
        assert response.json()["code"] == "my-link_1"
        assert response.json()["short_url"] == "http://test.local/my-link_1"

    def test_duplicate_custom_code_returns_409(self, client: TestClient) -> None:
        create(client, custom_code="taken")

        response = create(client, url="https://other.com", custom_code="taken")

        assert response.status_code == 409

    @pytest.mark.parametrize("code", ["docs", "DOCS", "redoc", "links"])
    def test_reserved_code_returns_409(self, client: TestClient, code: str) -> None:
        assert create(client, custom_code=code).status_code == 409

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"url": "not-a-url"},
            {"url": "ftp://example.com"},
            {"url": TARGET, "custom_code": "ab"},
            {"url": TARGET, "custom_code": "x" * 33},
            {"url": TARGET, "custom_code": "has space"},
            {"url": TARGET, "custom_code": "dot.json"},
        ],
    )
    def test_invalid_payload_returns_422(self, client: TestClient, payload: dict) -> None:
        assert client.post("/links", json=payload).status_code == 422

    def test_returns_503_when_no_free_code(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create(client, custom_code="always")
        monkeypatch.setattr(services, "generate_code", lambda: "always")

        assert create(client).status_code == 503


class TestRedirect:
    def test_redirects_and_counts_clicks(self, client: TestClient, db: Session) -> None:
        code = create(client, custom_code="golink").json()["code"]

        for _ in range(2):
            response = client.get(f"/{code}", follow_redirects=False)
            assert response.status_code == 307
            assert response.headers["location"] == TARGET

        redirects.flush_pending_clicks()

        assert db.scalar(select(Link.clicks).where(Link.code == code)) == 2

    def test_unknown_code_returns_404(self, client: TestClient) -> None:
        response = client.get("/doesnotexist", follow_redirects=False)

        assert response.status_code == 404
        assert response.json() == {"detail": "Link não encontrado"}

    def test_docs_route_is_not_captured(self, client: TestClient) -> None:
        response = client.get("/docs")

        assert response.status_code == 200
        assert "swagger" in response.text.lower()
