import pytest
from sqlalchemy.orm import Session

from app import services
from app.config import settings


def test_generate_code_uses_configured_length_and_alphabet() -> None:
    codes = {services.generate_code() for _ in range(100)}

    assert all(len(code) == settings.code_length for code in codes)
    assert all(set(code) <= set(services.ALPHABET) for code in codes)
    assert len(codes) > 1


def test_create_link_retries_on_collision(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    services.create_link(db, "https://a.com", "taken01")
    candidates = iter(["taken01", "free001"])
    monkeypatch.setattr(services, "generate_code", lambda: next(candidates))

    link = services.create_link(db, "https://b.com")

    assert link.code == "free001"
    assert link.target_url == "https://b.com"


def test_create_link_gives_up_after_max_attempts(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    services.create_link(db, "https://a.com", "taken01")
    calls: list[str] = []

    def always_taken() -> str:
        calls.append("taken01")
        return "taken01"

    monkeypatch.setattr(services, "generate_code", always_taken)

    with pytest.raises(services.CodeGenerationError):
        services.create_link(db, "https://b.com")
    assert len(calls) == services.MAX_GENERATION_ATTEMPTS


def test_custom_code_conflict_raises(db: Session) -> None:
    services.create_link(db, "https://a.com", "mine")

    with pytest.raises(services.CodeUnavailableError):
        services.create_link(db, "https://b.com", "mine")


def test_find_target_url_returns_the_url(db: Session) -> None:
    services.create_link(db, "https://a.com", "abc123")

    assert services.find_target_url(db, "abc123") == "https://a.com"


def test_find_unknown_target_url_returns_none(db: Session) -> None:
    assert services.find_target_url(db, "nope") is None


def test_add_clicks_accumulates_per_code(db: Session) -> None:
    first = services.create_link(db, "https://a.com", "abc123")
    second = services.create_link(db, "https://b.com", "def456")

    services.add_clicks(db, {"abc123": 3, "def456": 1})
    services.add_clicks(db, {"abc123": 2})

    db.refresh(first)
    db.refresh(second)
    assert first.clicks == 5
    assert second.clicks == 1
