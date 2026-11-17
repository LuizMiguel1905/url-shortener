import asyncio
import logging

from app import cache, services
from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def lookup_target_url(code: str) -> str | None:
    target_url = cache.get_target_url(code)
    if target_url is None:
        target_url = _load_and_cache(code)
        if target_url is None:
            return None
    if not cache.record_click(code):
        _add_clicks_in_database({code: 1})
    return target_url


def flush_pending_clicks() -> int:
    flushed = 0
    while pending := cache.take_pending_clicks(cache.FLUSH_BATCH_SIZE):
        try:
            _add_clicks_in_database(pending)
        except Exception:
            cache.restore_pending_clicks(pending)
            raise
        flushed += sum(pending.values())
    return flushed


async def flush_pending_clicks_forever() -> None:
    while True:
        await asyncio.sleep(settings.clicks_flush_interval_seconds)
        await flush_without_raising()


async def flush_without_raising() -> None:
    try:
        await asyncio.to_thread(flush_pending_clicks)
    except Exception:
        logger.exception("Falha ao gravar os cliques pendentes no banco")


def _load_and_cache(code: str) -> str | None:
    with SessionLocal() as db:
        target_url = services.find_target_url(db, code)
    if target_url is not None:
        cache.set_target_url(code, target_url)
    return target_url


def _add_clicks_in_database(clicks_by_code: dict[str, int]) -> None:
    with SessionLocal() as db:
        services.add_clicks(db, clicks_by_code)
