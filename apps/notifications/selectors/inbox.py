from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from ..models import Notification


INBOX_DEFAULT_PAGE_SIZE = 50
INBOX_MAX_PAGE_SIZE = 100


def get_notifications_page(  # pylint: disable=too-many-arguments
    *,
    user_id: int,
    limit: int = INBOX_DEFAULT_PAGE_SIZE,
    after_last_event_at=None,
    after_id: int = 0,
    before_last_event_at=None,
    before_id: int = 0,
    include_read: bool = True,
) -> dict[str, Any]:
    """Returns a page of notifications for the inbox UI.

    Notifications are ordered newest-first by the stable compound ordering:

        (-last_event_at, -id)

    Cursor pagination must use both cursor fields together:

        before_last_event_at + before_id
        after_last_event_at + after_id

    The id is a tie-breaker for notifications with the same last_event_at.
    Do not paginate by id alone, because aggregate notifications can update
    last_event_at and move earlier in the inbox.

    Pagination modes:
    - Initial page: no cursor.
    - Older page: rows strictly older than (before_last_event_at, before_id).
    - Newer page: rows strictly newer than (after_last_event_at, after_id).

    Items are returned newest-first with a has_more flag.
    """
    limit = max(1, min(limit, INBOX_MAX_PAGE_SIZE))
    qs = _notifications_values_qs(user_id=user_id, include_read=include_read)

    order_by = ("-last_event_at", "-id")

    # Newer-than cursor:
    # Fetch rows that sort before the cursor in newest-first order.
    # Because ordering is (-last_event_at, -id), a row is newer if:
    # - last_event_at is greater, or
    # - last_event_at is equal and id is greater.
    if after_last_event_at and after_id > 0:
        # Fetch one extra row to determine has_more
        rows = list(
            qs.filter(
                Q(last_event_at__gt=after_last_event_at)
                | Q(last_event_at=after_last_event_at, id__gt=after_id)
            ).order_by(*order_by)[: limit + 1]
        )
        has_more = len(rows) > limit
        rows = rows[:limit]

        return {
            "items": [_notification_row_to_dict(r) for r in rows],
            "next_before_cursor": None,
            "has_more": has_more,
        }

    # Older-than cursor:
    # Fetch rows that sort after the cursor in newest-first order.
    # Because ordering is (-last_event_at, -id), a row is older if:
    # - last_event_at is lower, or
    # - last_event_at is equal and id is lower.
    if before_last_event_at and before_id > 0:
        qs = qs.filter(
            Q(last_event_at__lt=before_last_event_at)
            | Q(last_event_at=before_last_event_at, id__lt=before_id)
        )

    rows = list(qs.order_by(*order_by)[: limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]

    next_before_cursor = _cursor_from_row(rows[-1]) if rows else None

    return {
        "items": [_notification_row_to_dict(r) for r in rows],
        "next_before_cursor": next_before_cursor,
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
        "last_event_at",
        "read_at",
    )


def _notification_row_to_dict(r: dict[str, Any]) -> dict[str, Any]:
    payload = r["payload"] or {}
    if not isinstance(payload, dict):
        payload = {}

    created_at = r["created_at"] or timezone.now()
    last_event_at = r["last_event_at"] or created_at

    return {
        "id": r["id"],
        "notification_type": r["notification_type"] or "",
        "level": r["level"] or "",
        "title": r["title"] or "",
        "body": r["body"] or "",
        "payload": payload,
        "timestamp": created_at.isoformat(),
        "last_event_at": last_event_at.isoformat(),
        "is_read": r["read_at"] is not None,
    }


def _cursor_from_row(row: dict[str, Any]) -> dict[str, Any]:
    last_event_at = row["last_event_at"] or row["created_at"] or timezone.now()
    return {"last_event_at": last_event_at.isoformat(), "id": row["id"]}
