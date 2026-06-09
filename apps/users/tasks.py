import logging

from celery import shared_task
from django.db import DatabaseError
from django_redis.exceptions import ConnectionInterrupted
from redis.exceptions import RedisError

from core.cache_locks import cache_lock


DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY = (
    "users:delete_expired_pending_email_changes:lock"
)
DELETE_PENDING_EMAIL_CHANGES_LOCK_TIMEOUT_SECONDS = 10 * 60  # 10 min


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

    lock_value = self.request.id or None

    with cache_lock(
        lock_key=DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY,
        lock_value=lock_value,
        timeout=DELETE_PENDING_EMAIL_CHANGES_LOCK_TIMEOUT_SECONDS,
    ) as lock:
        if not lock.acquired:
            logger.info("Pending email change deletion skipped: already running.")
            return

        deleted_count = delete_expired_pending_email_changes()

        if deleted_count:
            logger.info(
                "Deleted %s expired pending email change%s.",
                deleted_count,
                "" if deleted_count == 1 else "s",
            )
