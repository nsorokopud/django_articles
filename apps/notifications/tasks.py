import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError

from core.services.email import EmailConfig, send_email

from .services.delivery_email import build_notification_email_config


NOTIFICATIONS_UNREAD_COUNT_SYNC_LOCK_KEY = "notifications_unread_counts_sync_lock"
NOTIFICATIONS_CLEANUP_LOCK_KEY = "notifications_cleanup_lock"

logger = logging.getLogger(__name__)


@shared_task(max_retries=0)
def send_notification_ws_task(
    notification_id: int,
    is_new_unread: bool = True,
) -> None:
    from .services.delivery_ws import send_ws_notification

    try:
        async_to_sync(send_ws_notification)(
            notification_id,
            is_new_unread=is_new_unread,
        )
    except Exception:
        logger.exception("WS delivery failed (notification_id=%s)", notification_id)


@shared_task(
    autoretry_for=(DatabaseError,),
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


@shared_task(max_retries=0)
def cleanup_old_read_notifications_task() -> int:
    from .services.retention import cleanup_old_read_notifications

    if not cache.add(
        NOTIFICATIONS_CLEANUP_LOCK_KEY,
        "1",
        timeout=int(settings.NOTIFICATIONS_CLEANUP_LOCK_TTL_SECONDS),
    ):
        logger.info("Notification cleanup skipped: already running")
        return 0
    try:
        return cleanup_old_read_notifications()
    finally:
        cache.delete(NOTIFICATIONS_CLEANUP_LOCK_KEY)


@shared_task(max_retries=0)
def sync_unread_notification_counts_task() -> dict[str, int]:
    from .services.counters import sync_unread_notification_counts

    if not cache.add(
        NOTIFICATIONS_UNREAD_COUNT_SYNC_LOCK_KEY,
        "1",
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
        cache.delete(NOTIFICATIONS_UNREAD_COUNT_SYNC_LOCK_KEY)
