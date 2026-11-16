"""Regras de negócio dos links, independentes de HTTP."""

import secrets
import string

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Link

ALPHABET = string.ascii_letters + string.digits

RESERVED_CODES = frozenset({"docs", "redoc", "links"})
MAX_GENERATION_ATTEMPTS = 5


class CodeUnavailableError(Exception):
    """O código personalizado já existe ou é reservado."""


class CodeGenerationError(Exception):
    """Não foi possível gerar um código aleatório livre."""


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


def resolve_link(db: Session, code: str) -> str | None:
    """Retorna a URL de destino e incrementa o contador de cliques, numa única query."""
    target_url = db.execute(
        update(Link)
        .where(Link.code == code)
        .values(clicks=Link.clicks + 1)
        .returning(Link.target_url)
    ).scalar_one_or_none()
    if target_url is not None:
        db.commit()
    return target_url


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
