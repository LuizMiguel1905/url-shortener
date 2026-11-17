import logging

from redis import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

TARGET_URL_KEY = "link:{code}"
PENDING_CLICKS_KEY = "clicks:{code}"
DIRTY_CODES_KEY = "clicks:dirty"
FLUSH_BATCH_SIZE = 500

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=0.2,
    socket_timeout=0.2,
)


def get_target_url(code: str) -> str | None:
    try:
        return redis_client.get(TARGET_URL_KEY.format(code=code))
    except RedisError:
        logger.warning("Cache indisponível ao ler o link %s", code)
        return None


def set_target_url(code: str, target_url: str) -> None:
    try:
        redis_client.set(
            TARGET_URL_KEY.format(code=code), target_url, ex=settings.cache_ttl_seconds
        )
    except RedisError:
        logger.warning("Cache indisponível ao gravar o link %s", code)


def record_click(code: str) -> bool:
    try:
        pipeline = redis_client.pipeline()
        pipeline.incr(PENDING_CLICKS_KEY.format(code=code))
        pipeline.sadd(DIRTY_CODES_KEY, code)
        pipeline.execute()
    except RedisError:
        logger.warning("Cache indisponível ao contar clique do link %s", code)
        return False
    return True


def take_pending_clicks(limit: int) -> dict[str, int]:
    codes = redis_client.spop(DIRTY_CODES_KEY, limit)
    if not codes:
        return {}
    pipeline = redis_client.pipeline()
    for code in codes:
        pipeline.getdel(PENDING_CLICKS_KEY.format(code=code))
    counts = pipeline.execute()
    return {code: int(count) for code, count in zip(codes, counts, strict=True) if count}


def restore_pending_clicks(clicks_by_code: dict[str, int]) -> None:
    pipeline = redis_client.pipeline()
    for code, amount in clicks_by_code.items():
        pipeline.incrby(PENDING_CLICKS_KEY.format(code=code), amount)
        pipeline.sadd(DIRTY_CODES_KEY, code)
    pipeline.execute()
