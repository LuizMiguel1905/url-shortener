import secrets
import string

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Link

ALPHABET = string.ascii_letters + string.digits

RESERVED_CODES = frozenset({"docs", "redoc", "links"})
MAX_GENERATION_ATTEMPTS = 5


class CodeUnavailableError(Exception):
    pass


class CodeGenerationError(Exception):
    pass


def generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(settings.code_length))


def create_link(db: Session, target_url: str, custom_code: str | None = None) -> Link:
    if custom_code is not None:
        if custom_code.lower() in RESERVED_CODES:
            raise CodeUnavailableError(custom_code)
        link = _try_insert(db, custom_code, target_url)
        if link is None:
            raise CodeUnavailableError(custom_code)
        return link

    for _ in range(MAX_GENERATION_ATTEMPTS):
        link = _try_insert(db, generate_code(), target_url)
        if link is not None:
            return link
    raise CodeGenerationError


def find_target_url(db: Session, code: str) -> str | None:
    return db.scalar(select(Link.target_url).where(Link.code == code))


def add_clicks(db: Session, clicks_by_code: dict[str, int]) -> None:
    for code, amount in clicks_by_code.items():
        db.execute(update(Link).where(Link.code == code).values(clicks=Link.clicks + amount))
    db.commit()


def _try_insert(db: Session, code: str, target_url: str) -> Link | None:
    link = Link(code=code, target_url=target_url)
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(link)
    return link
