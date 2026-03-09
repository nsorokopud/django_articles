import logging
from typing import Any, Optional

from django.db import IntegrityError, transaction
from django.db.models import F
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from users.models import User

from ..models import NOTIFICATION_DEDUPE_CONSTRAINT, Notification, NotificationType


logger = logging.getLogger(__name__)


def create_new_comment_notification(
    *,
    comment_id: int,
    comment_author_id: int,
    comment_author_username: str,
    article_author_id: int,
    article_slug: str,
    article_title: str,
) -> Optional[tuple[Notification, bool]]:

    if comment_author_id == article_author_id:
        return None

    try:
        body = _render_notification_message(
            "notifications/new_comment_notification.html",
            {
                "article_title": article_title,
                "comment_author": comment_author_username,
            },
        )
    except (TemplateDoesNotExist, TemplateSyntaxError) as e:
        logger.warning("Failed to render notification body: %s", e, exc_info=True)
        body = str(
            format_html(
                "New comment by {} on article '{}'.",
                comment_author_username,
                article_title,
            )
        )

    try:
        link = reverse("article-details", args=(article_slug,))
    except NoReverseMatch:
        logger.exception("reverse(article-details) failed for slug=%s", article_slug)
        link = "/"

    return create_notification(
        recipient_id=article_author_id,
        notification_type=NotificationType.NEW_COMMENT,  # type: ignore[arg-type]
        level=Notification.Level.INFO,  # type: ignore[arg-type]
        title="New Comment",
        body=body,
        payload={"link": link},
        sender_id=comment_author_id,
        dedupe_key=f"new_comment:{comment_id}",
    )


def create_system_notification(
    *,
    recipient_id: int,
    level: str = Notification.Level.INFO,  # type: ignore[assignment]
    title: str,
    body: str,
    payload: Optional[dict[str, Any]] = None,
    sender_id: Optional[int] = None,
    dedupe_key: str = "",
) -> tuple[Notification, bool]:
    notification, created = create_notification(
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


def create_notification(
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
