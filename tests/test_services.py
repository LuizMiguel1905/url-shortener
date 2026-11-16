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


def test_resolve_link_increments_clicks(db: Session) -> None:
    link = services.create_link(db, "https://a.com", "abc123")

    assert services.resolve_link(db, "abc123") == "https://a.com"

    db.refresh(link)
    assert link.clicks == 1


def test_resolve_unknown_link_returns_none(db: Session) -> None:
    assert services.resolve_link(db, "nope") is None
