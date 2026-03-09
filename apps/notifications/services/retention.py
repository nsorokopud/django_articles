import logging
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from notifications.models import Notification


logger = logging.getLogger(__name__)


def cleanup_old_read_notifications(
    *, older_than_days: Optional[int] = None, max_batches: Optional[int] = None
) -> int:
    older_than_days = (
        settings.NOTIFICATION_READ_RETENTION_DAYS
        if older_than_days is None
        else older_than_days
    )
    max_batches = (
        settings.NOTIFICATION_CLEANUP_MAX_BATCHES
        if max_batches is None
        else max_batches
    )

    if older_than_days <= 0:
        raise ValueError("older_than_days must be > 0")
    if max_batches is None:
        raise ValueError("max_batches must not be None")
    if max_batches < 0:
        raise ValueError("max_batches must be >= 0")
    if max_batches == 0:
        logger.info("Notification cleanup skipped: max_batches=0")
        return 0

    cutoff = timezone.now() - timedelta(days=older_than_days)
    total_deleted = 0
    exhausted = False

    for _ in range(max_batches):
        deleted = _delete_old_read_notifications_batch(cutoff=cutoff)
        total_deleted += deleted

        if deleted == 0:
            exhausted = True
            break

    if total_deleted:
        logger.info(
            (
                "Deleted %s old read notifications "
                "(retention_days=%s, batch_size=%s, max_batches=%s, exhausted=%s)"
            ),
            total_deleted,
            older_than_days,
            settings.NOTIFICATION_CLEANUP_BATCH_SIZE,
            max_batches,
            exhausted,
        )
    else:
        logger.debug("No old read notifications to delete")

    return total_deleted


def _delete_old_read_notifications_batch(
    *,
    cutoff: datetime,
    batch_size: Optional[int] = None,
) -> int:
    batch_size = (
        settings.NOTIFICATION_CLEANUP_BATCH_SIZE if batch_size is None else batch_size
    )
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    ids = list(
        Notification.objects.filter(
            read_at__isnull=False,
            read_at__lt=cutoff,
        )
        .order_by("read_at", "id")
        .values_list("id", flat=True)[:batch_size]
    )

    if not ids:
        return 0

    deleted_count, _ = Notification.objects.filter(id__in=ids).delete()
    return deleted_count
