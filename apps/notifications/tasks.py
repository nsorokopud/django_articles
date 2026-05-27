import logging
import smtplib
from uuid import uuid4

from asgiref.sync import async_to_sync
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django_redis import get_redis_connection
from django_redis.exceptions import ConnectionInterrupted
from redis import RedisError

from core.services.email import EmailConfig, send_email

from .services.delivery_email import build_notification_email_config


NOTIFICATIONS_UNREAD_COUNT_SYNC_LOCK_KEY = "notifications_unread_counts_sync_lock"
NOTIFICATIONS_CLEANUP_LOCK_KEY = "notifications_cleanup_lock"

RELEASE_LOCK_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

logger = logging.getLogger(__name__)


@shared_task(max_retries=0)
def send_notification_ws_task(notification_id: int, is_new_unread: bool = True) -> None:
    from .services.delivery_ws import send_ws_notification

    try:
        async_to_sync(send_ws_notification)(
            notification_id, is_new_unread=is_new_unread
        )
    except Exception:  # pylint: disable=W0718
        logger.exception("WS delivery failed (notification_id=%s)", notification_id)


@shared_task(
    autoretry_for=(DatabaseError, OSError, smtplib.SMTPException),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def send_notification_email_task(notification_id: int) -> None:
    cfg_dict = build_notification_email_config(notification_id)
    if not cfg_dict:
        return

    cfg = EmailConfig.from_dict(cfg_dict)
    send_email(cfg)


@shared_task(
    bind=True,
    soft_time_limit=300,
    time_limit=310,
    autoretry_for=(
        OSError,
        DatabaseError,
        RedisError,
        ConnectionInterrupted,
        SoftTimeLimitExceeded,
    ),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def cleanup_old_read_notifications_task(self) -> int:
    from .services.retention import cleanup_old_read_notifications

    lock_value = self.request.id or uuid4().hex

    if not cache.add(
        NOTIFICATIONS_CLEANUP_LOCK_KEY,
        lock_value,
        timeout=int(settings.NOTIFICATIONS_CLEANUP_LOCK_TTL_SECONDS),
    ):
        logger.info("Notification cleanup skipped: already running")
        return 0
    try:
        return cleanup_old_read_notifications()
    finally:
        _release_lock(lock_key=NOTIFICATIONS_CLEANUP_LOCK_KEY, lock_value=lock_value)


@shared_task(
    bind=True,
    soft_time_limit=300,
    time_limit=310,
    autoretry_for=(
        OSError,
        DatabaseError,
        RedisError,
        ConnectionInterrupted,
        SoftTimeLimitExceeded,
    ),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def sync_unread_notification_counts_task(self) -> dict[str, int]:
    from .services.counters import sync_unread_notification_counts

    lock_value = self.request.id or uuid4().hex

    if not cache.add(
        NOTIFICATIONS_UNREAD_COUNT_SYNC_LOCK_KEY,
        lock_value,
        timeout=int(settings.NOTIFICATIONS_UNREAD_COUNT_SYNC_LOCK_TTL_SECONDS),
    ):
        logger.info("Unread-count sync skipped: already running")
        return {"users_checked": 0, "users_updated": 0, "users_zeroed": 0}

    try:
        stats = sync_unread_notification_counts(
            batch_size=int(settings.NOTIFICATIONS_UNREAD_COUNT_SYNC_BATCH_SIZE),
        )
        logger.info("Unread-count sync finished: %s", stats)
        return stats
    finally:
        _release_lock(
            lock_key=NOTIFICATIONS_UNREAD_COUNT_SYNC_LOCK_KEY, lock_value=lock_value
        )


def _release_lock(*, lock_key: str, lock_value: str) -> None:
    try:
        redis_conn = get_redis_connection("default")
        redis_conn.eval(RELEASE_LOCK_LUA, 1, lock_key, lock_value)
    except (RedisError, ConnectionInterrupted):
        logger.exception("Failed to release lock %s.", lock_key)
