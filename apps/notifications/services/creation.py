import logging
from typing import Any, Optional

from django.db import IntegrityError, transaction
from django.db.models import F
from django.template.loader import render_to_string

from users.models import User

from ..models import NOTIFICATION_DEDUPE_CONSTRAINT, Notification, NotificationType
from .comment_aggregation import create_or_update_unread_comment_aggregate_notification


logger = logging.getLogger(__name__)


def create_new_comment_notification(
    *,
    comment_id: int,
    comment_author_id: int,
    comment_author_username: str,
    article_author_id: int,
    article_id: int,
    article_slug: str,
    article_title: str,
) -> Optional[tuple[Notification, bool]]:

    return create_or_update_unread_comment_aggregate_notification(
        comment_id=comment_id,
        comment_author_id=comment_author_id,
        comment_author_username=comment_author_username,
        article_id=article_id,
        article_author_id=article_author_id,
        article_slug=article_slug,
        article_title=article_title,
    )


def create_deduped_system_notification(
    *,
    recipient_id: int,
    level: str = Notification.Level.INFO,  # type: ignore[assignment]
    title: str,
    body: str,
    payload: Optional[dict[str, Any]] = None,
    sender_id: Optional[int] = None,
    dedupe_key: str = "",
) -> tuple[Notification, bool]:
    notification, created = create_deduped_notification(
        recipient_id=recipient_id,
        notification_type=NotificationType.SYSTEM,  # type: ignore[arg-type]
        level=level,
        title=title,
        body=body,
        payload=payload,
        sender_id=sender_id,
        dedupe_key=dedupe_key,
    )
    return notification, created


def create_deduped_notification(
    *,
    recipient_id: int,
    notification_type: str = NotificationType.SYSTEM,  # type: ignore[assignment]
    level: str = Notification.Level.INFO,  # type: ignore[assignment]
    title: str,
    body: str,
    payload: Optional[dict[str, Any]] = None,
    sender_id: Optional[int] = None,
    dedupe_key: str = "",
) -> tuple[Notification, bool]:

    payload = _normalize_payload(payload, recipient_id=recipient_id)
    dedupe_key = (dedupe_key or "").strip()

    try:
        with transaction.atomic():
            n = Notification.objects.create(
                recipient_id=recipient_id,
                sender_id=sender_id,
                notification_type=notification_type,
                level=level,
                title=title,
                body=body,
                payload=payload,
                dedupe_key=dedupe_key,
            )
            _increment_unread_notification_count(recipient_id)
        return n, True

    except IntegrityError as e:
        if not dedupe_key or not _is_dedupe_violation(e):
            raise

        n = Notification.objects.get(
            recipient_id=recipient_id,
            dedupe_key=dedupe_key,
        )
        return n, False


def _render_notification_message(template_name: str, context: dict[str, Any]) -> str:
    """Renders a notification message from a template."""
    return render_to_string(template_name, context).strip("\n").replace("\n", " ")


def _normalize_payload(payload: Any, *, recipient_id: int) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    logger.warning(
        "Invalid payload (type=%s, recipient_id=%s)",
        type(payload).__name__,
        recipient_id,
    )
    return {}


def _increment_unread_notification_count(user_id: int) -> None:
    User.objects.filter(id=user_id).update(
        unread_notifications_count=F("unread_notifications_count") + 1
    )


def _is_dedupe_violation(exc: IntegrityError) -> bool:
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    diag = getattr(cause, "diag", None)
    if (
        diag
        and getattr(diag, "constraint_name", None) == NOTIFICATION_DEDUPE_CONSTRAINT
    ):
        return True

    return NOTIFICATION_DEDUPE_CONSTRAINT in str(exc)
