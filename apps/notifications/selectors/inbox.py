from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from ..models import Notification


INBOX_DEFAULT_PAGE_SIZE = 50
INBOX_MAX_PAGE_SIZE = 100


def get_notifications_page(
    *,
    user_id: int,
    limit: int = INBOX_DEFAULT_PAGE_SIZE,
    after_id: int = 0,
    before_id: int = 0,
    include_read: bool = True,
) -> dict[str, Any]:
    """Returns a page of notifications for the inbox UI.

    Supports:
    - initial/older pagination via before_id (id < before_id)
    - polling for newer items via after_id (id > after_id)

    Items are returned newest-first with a has_more flag.
    """
    limit = max(1, min(limit, INBOX_MAX_PAGE_SIZE))
    qs = _notifications_values_qs(user_id=user_id, include_read=include_read)

    # Newer-than (fetch newest items with id > after_id)
    if after_id > 0:
        # Fetch one extra row to determine has_more
        rows = list(qs.filter(id__gt=after_id).order_by("-id")[: limit + 1])
        has_more = len(rows) > limit
        rows = rows[:limit]

        return {
            "items": [_notification_row_to_dict(r) for r in rows],
            "next_before_id": None,
            "has_more": has_more,
        }

    # Older-than (load more) or initial
    if before_id > 0:
        qs = qs.filter(id__lt=before_id)

    rows = list(qs.order_by("-id")[: limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]

    next_before_id = rows[-1]["id"] if rows else None

    return {
        "items": [_notification_row_to_dict(r) for r in rows],
        "next_before_id": next_before_id,
        "has_more": has_more,
    }


def _notifications_values_qs(
    *, user_id: int, include_read: bool
) -> QuerySet[dict[str, Any]]:
    qs = Notification.objects.filter(recipient_id=user_id)
    if not include_read:
        qs = qs.filter(read_at__isnull=True)

    return qs.values(
        "id",
        "notification_type",
        "level",
        "title",
        "body",
        "payload",
        "created_at",
        "read_at",
    )


def _notification_row_to_dict(r: dict[str, Any]) -> dict[str, Any]:
    payload = r["payload"] or {}
    if not isinstance(payload, dict):
        payload = {}

    created_at = r["created_at"] or timezone.now()

    return {
        "id": r["id"],
        "notification_type": r["notification_type"] or "",
        "level": r["level"] or "",
        "title": r["title"] or "",
        "body": r["body"] or "",
        "payload": payload,
        "timestamp": created_at.isoformat(),
        "is_read": r["read_at"] is not None,
    }
