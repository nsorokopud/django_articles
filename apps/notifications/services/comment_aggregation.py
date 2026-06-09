from typing import Any, Optional

from django.db import IntegrityError, transaction
from django.db.models import F
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.db import get_constraint_name
from users.models import User

from ..models import (
    UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT,
    Notification,
    NotificationType,
)


MAX_SAMPLE_COMMENTERS = 2


def create_or_update_unread_comment_aggregate_notification(
    *,
    comment_id: int,
    comment_author_id: int,
    comment_author_username: str,
    article_id: int,
    article_author_id: int,
    article_slug: str,
    article_title: str,
) -> Optional[tuple[Notification, bool]]:
    if comment_author_id == article_author_id:
        return None

    aggregate_key = _build_comment_aggregate_key(
        recipient_id=article_author_id,
        article_id=article_id,
    )
    link = _build_article_link(article_slug)
    now = timezone.now()
    now_iso = now.isoformat()

    def _update_existing(existing: Notification) -> Notification:
        return _update_comment_aggregate_notification(
            notification=existing,
            comment_id=comment_id,
            comment_author_id=comment_author_id,
            comment_author_username=comment_author_username,
            article_id=article_id,
            article_title=article_title,
            link=link,
            now=now,
            now_iso=now_iso,
        )

    with transaction.atomic():
        existing = _find_existing_unread_comment_aggregate_for_update(
            recipient_id=article_author_id, aggregate_key=aggregate_key
        )
        if existing is not None:
            return _update_existing(existing), False

        try:
            with transaction.atomic():
                notification = Notification.objects.create(
                    recipient_id=article_author_id,
                    sender_id=None,
                    notification_type=NotificationType.NEW_COMMENT,
                    level=Notification.Level.INFO,
                    title="New Comment",
                    body=f"New comment by {comment_author_username} "
                    f'on your article "{article_title}".',
                    payload=_build_initial_comment_aggregate_payload(
                        comment_id=comment_id,
                        comment_author_id=comment_author_id,
                        comment_author_username=comment_author_username,
                        article_id=article_id,
                        article_title=article_title,
                        link=link,
                        now_iso=now_iso,
                    ),
                    aggregate_key=aggregate_key,
                    dedupe_key="",
                    last_event_at=now,
                )
                _increment_unread_notification_count(article_author_id)

            return notification, True

        except IntegrityError as exc:
            if (
                get_constraint_name(exc)
                != UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT
            ):
                raise

            existing = _find_existing_unread_comment_aggregate_for_update(
                recipient_id=article_author_id, aggregate_key=aggregate_key
            )
            if existing is None:
                raise RuntimeError(
                    "unread comment aggregate conflict occurred, "
                    "but no aggregate row was found."
                ) from exc

            return _update_existing(existing), False


def _find_existing_unread_comment_aggregate_for_update(
    *, recipient_id: int, aggregate_key: str
) -> Optional[Notification]:
    return (
        Notification.objects.select_for_update()
        .only("id", "payload", "title", "body", "sender_id")
        .filter(
            recipient_id=recipient_id,
            notification_type=NotificationType.NEW_COMMENT,
            aggregate_key=aggregate_key,
            read_at__isnull=True,
        )
        .order_by("-id")
        .first()
    )


def _update_comment_aggregate_notification(
    *,
    notification: Notification,
    comment_id: int,
    comment_author_id: int,
    comment_author_username: str,
    article_id: int,
    article_title: str,
    link: str,
    now,
    now_iso: str,
) -> Notification:
    payload = _normalize_comment_aggregate_payload(notification.payload)
    payload["kind"] = "comment_aggregate"
    payload["link"] = link
    payload["article_id"] = article_id
    payload["article_title"] = article_title
    payload["last_comment_id"] = comment_id
    payload["last_comment_at"] = now_iso
    payload["comment_count"] = max(0, _safe_int(payload.get("comment_count"), 0)) + 1

    _update_commenter_summary(
        payload=payload,
        comment_author_id=comment_author_id,
        comment_author_username=comment_author_username,
    )

    count = payload["comment_count"]
    sample_commenters = payload["sample_commenters"]
    has_other_commenters = payload["has_other_commenters"]

    notification.sender = None
    notification.title = _build_comment_aggregate_title(count)
    notification.body = _build_comment_aggregate_body(
        count=count,
        article_title=article_title,
        sample_commenters=sample_commenters,
        has_other_commenters=has_other_commenters,
    )
    notification.payload = payload
    notification.last_event_at = now
    notification.save(
        update_fields=["sender", "title", "body", "payload", "last_event_at"]
    )
    return notification


def _build_comment_aggregate_key(*, recipient_id: int, article_id: int) -> str:
    return f"new_comment_agg:{recipient_id}:{article_id}"


def _build_article_link(article_slug: str) -> str:
    try:
        return reverse("article-details", args=(article_slug,))
    except NoReverseMatch:
        return "/"


def _build_initial_comment_aggregate_payload(
    *,
    comment_id: int,
    comment_author_id: int,
    comment_author_username: str,
    article_id: int,
    article_title: str,
    link: str,
    now_iso: str,
) -> dict[str, Any]:
    return {
        "kind": "comment_aggregate",
        "link": link,
        "article_id": article_id,
        "article_title": article_title,
        "comment_count": 1,
        "has_other_commenters": False,
        "last_comment_id": comment_id,
        "last_comment_at": now_iso,
        "sample_commenters": [
            {"id": comment_author_id, "username": comment_author_username}
        ],
    }


def _normalize_comment_aggregate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}

    raw_sample = payload.get("sample_commenters")
    if not isinstance(raw_sample, list):
        raw_sample = []

    normalized_sample: list[dict[str, Any]] = []
    for item in raw_sample:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item["id"])
            username = str(item["username"])
        except (KeyError, TypeError, ValueError):
            continue
        normalized_sample.append({"id": item_id, "username": username})

    return {
        "kind": "comment_aggregate",
        "link": payload.get("link") or "",
        "article_id": _safe_int(payload.get("article_id"), 0),
        "article_title": str(payload.get("article_title") or ""),
        "comment_count": max(0, _safe_int(payload.get("comment_count"), 0)),
        "has_other_commenters": bool(payload.get("has_other_commenters")),
        "last_comment_id": _safe_int(payload.get("last_comment_id"), 0),
        "last_comment_at": str(payload.get("last_comment_at") or ""),
        "sample_commenters": normalized_sample[:MAX_SAMPLE_COMMENTERS],
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _update_commenter_summary(
    *, payload: dict[str, Any], comment_author_id: int, comment_author_username: str
) -> None:
    sample_commenters = payload.get("sample_commenters") or []
    has_other_commenters = bool(payload.get("has_other_commenters"))

    if not isinstance(sample_commenters, list):
        sample_commenters = []

    sample_commenters = sample_commenters[:MAX_SAMPLE_COMMENTERS]

    sample_ids = {
        _safe_int(item.get("id"), 0)
        for item in sample_commenters
        if isinstance(item, dict)
    }

    if comment_author_id in sample_ids:
        payload["sample_commenters"] = sample_commenters
        payload["has_other_commenters"] = has_other_commenters
        return

    if len(sample_commenters) < MAX_SAMPLE_COMMENTERS:
        sample_commenters.append(
            {"id": comment_author_id, "username": comment_author_username}
        )
        payload["sample_commenters"] = sample_commenters
        payload["has_other_commenters"] = has_other_commenters
        return

    payload["sample_commenters"] = sample_commenters
    payload["has_other_commenters"] = True


def _build_comment_aggregate_title(count: int) -> str:
    return "New Comment" if count == 1 else "New Comments"


def _build_comment_aggregate_body(
    *,
    count: int,
    article_title: str,
    sample_commenters: list[Any],
    has_other_commenters: bool,
) -> str:
    usernames = [
        str(item.get("username"))
        for item in sample_commenters
        if isinstance(item, dict) and item.get("username")
    ]

    if count == 1:
        if usernames:
            return f'New comment by {usernames[0]} on your article "{article_title}".'
        return f'New comment on your article "{article_title}".'

    if len(usernames) >= 2:
        if has_other_commenters:
            return (
                f"{usernames[0]}, {usernames[1]}, and others commented on your "
                f'article "{article_title}".'
            )

        return (
            f"{usernames[0]} and {usernames[1]} commented on your article "
            f'"{article_title}".'
        )

    if len(usernames) == 1:
        return (
            f"{usernames[0]} left {count} comments on your article "
            f'"{article_title}".'
        )

    return f'{count} new comments on your article "{article_title}".'


def _increment_unread_notification_count(user_id: int) -> None:
    User.objects.filter(id=user_id).update(
        unread_notifications_count=F("unread_notifications_count") + 1
    )
