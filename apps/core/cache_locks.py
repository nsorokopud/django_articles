import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator
from uuid import uuid4

from django_redis import get_redis_connection
from django_redis.exceptions import ConnectionInterrupted
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)


RELEASE_LOCK_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


@dataclass(frozen=True)
class CacheLock:
    acquired: bool
    lock_key: str
    lock_value: str


def release_redis_lock(
    *, lock_key: str, lock_value: str, cache_alias: str = "default"
) -> None:
    try:
        redis_conn = get_redis_connection(cache_alias)
        redis_conn.eval(RELEASE_LOCK_LUA, 1, lock_key, lock_value)
    except (RedisError, ConnectionInterrupted):
        logger.exception("Failed to release lock %s.", lock_key)


@contextmanager
def cache_lock(
    *,
    lock_key: str,
    timeout: int,
    lock_value: str | None = None,
    cache_alias: str = "default",
) -> Generator[CacheLock, Any, None]:
    if timeout <= 0:
        raise ValueError("timeout must be > 0")

    value = lock_value or uuid4().hex
    redis_conn = get_redis_connection(cache_alias)

    acquired = bool(redis_conn.set(lock_key, value, nx=True, ex=timeout))

    try:
        yield CacheLock(acquired=acquired, lock_key=lock_key, lock_value=value)
    finally:
        if acquired:
            release_redis_lock(
                lock_key=lock_key,
                lock_value=value,
                cache_alias=cache_alias,
            )
