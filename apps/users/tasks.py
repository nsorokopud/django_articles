import logging
from uuid import uuid4

from celery import shared_task
from django.core.cache import cache
from django.db import DatabaseError
from django_redis import get_redis_connection
from django_redis.exceptions import ConnectionInterrupted
from redis.exceptions import RedisError


DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY = (
    "users:delete_expired_pending_email_changes:lock"
)
DELETE_PENDING_EMAIL_CHANGES_LOCK_TIMEOUT_SECONDS = 10 * 60  # 10 min

RELEASE_LOCK_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(DatabaseError, RedisError, ConnectionInterrupted),
    retry_backoff=60,
    retry_jitter=True,
    max_retries=3,
    ignore_result=True,
)
def delete_expired_pending_email_changes_task(self) -> None:
    from .services.email_addresses import delete_expired_pending_email_changes

    lock_value = self.request.id or uuid4().hex

    if not cache.add(
        DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY,
        lock_value,
        timeout=DELETE_PENDING_EMAIL_CHANGES_LOCK_TIMEOUT_SECONDS,
    ):
        logger.info("Pending email change deletion skipped: already running.")
        return

    try:
        deleted_count = delete_expired_pending_email_changes()

        if deleted_count:
            logger.info(
                "Deleted %s expired pending email change%s.",
                deleted_count,
                "" if deleted_count == 1 else "s",
            )
    finally:
        _release_lock(
            lock_key=DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY, lock_value=lock_value
        )


def _release_lock(*, lock_key: str, lock_value: str) -> None:
    try:
        redis_conn = get_redis_connection("default")
        redis_conn.eval(RELEASE_LOCK_LUA, 1, lock_key, lock_value)
    except (RedisError, ConnectionInterrupted):
        logger.exception("Failed to release lock %s.", lock_key)
