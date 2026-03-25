from typing import Any, Optional

from django.db import IntegrityError, transaction
from django.db.models import F
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

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
    now_iso = timezone.now().isoformat()

    def _update_existing(existing: Notification) -> Notification:
        return _update_comment_aggregate_notification(
            notification=existing,
            comment_id=comment_id,
            comment_author_id=comment_author_id,
            comment_author_username=comment_author_username,
            article_id=article_id,
            article_title=article_title,
            link=link,
            now_iso=now_iso,
        )

    with transaction.atomic():
        existing = _find_existing_unread_comment_aggregate_for_update(
            recipient_id=article_author_id,
            aggregate_key=aggregate_key,
        )
        if existing is not None:
            return _update_existing(existing), False

        try:
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
            )
            _increment_unread_notification_count(article_author_id)
            return notification, True

        except IntegrityError as exc:
            if not _is_unread_aggregate_violation(exc):
                raise

            existing = _find_existing_unread_comment_aggregate_for_update(
                recipient_id=article_author_id,
                aggregate_key=aggregate_key,
            )
            if existing is None:
                raise RuntimeError(
                    "unread comment aggregate conflict occurred, "
                    "but no aggregate row was found."
                ) from exc

            return _update_existing(existing), False


def _find_existing_unread_comment_aggregate_for_update(
    *,
    recipient_id: int,
    aggregate_key: str,
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

    existing_ids = {
        int(item["id"])
        for item in payload.get("sample_commenters", [])
        if isinstance(item, dict) and "id" in item
    }

    distinct_count = max(
        0,
        _safe_int(payload.get("distinct_commenter_count"), len(existing_ids)),
    )

    if comment_author_id not in existing_ids:
        distinct_count += 1

    payload["distinct_commenter_count"] = distinct_count
    payload["sample_commenters"] = _prepend_unique_commenter(
        current=payload.get("sample_commenters") or [],
        commenter={
            "id": comment_author_id,
            "username": comment_author_username,
        },
        max_items=MAX_SAMPLE_COMMENTERS,
    )

    count = payload["comment_count"]
    sample_commenters = payload["sample_commenters"]
    distinct_commenter_count = payload["distinct_commenter_count"]

    notification.sender = None
    notification.title = _build_comment_aggregate_title(count)
    notification.body = _build_comment_aggregate_body(
        count=count,
        article_title=article_title,
        sample_commenters=sample_commenters,
        distinct_commenter_count=distinct_commenter_count,
    )
    notification.payload = payload
    notification.save(update_fields=["sender", "title", "body", "payload"])
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
        "distinct_commenter_count": 1,
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
        "last_comment_id": _safe_int(payload.get("last_comment_id"), 0),
        "last_comment_at": str(payload.get("last_comment_at") or ""),
        "sample_commenters": normalized_sample[:MAX_SAMPLE_COMMENTERS],
        "distinct_commenter_count": max(
            0,
            _safe_int(payload.get("distinct_commenter_count"), len(normalized_sample)),
        ),
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _prepend_unique_commenter(
    *,
    current: list[Any],
    commenter: dict[str, Any],
    max_items: int,
) -> list[dict[str, Any]]:
    incoming_id = int(commenter["id"])
    incoming_username = str(commenter["username"])

    result: list[dict[str, Any]] = [{"id": incoming_id, "username": incoming_username}]
    seen = {incoming_id}

    for item in current:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item["id"])
            username = str(item["username"])
        except (KeyError, TypeError, ValueError):
            continue

        if item_id in seen:
            continue

        result.append({"id": item_id, "username": username})
        seen.add(item_id)

        if len(result) >= max_items:
            break

    return result[:max_items]


def _build_comment_aggregate_title(count: int) -> str:
    return "New Comment" if count == 1 else "New Comments"


def _build_comment_aggregate_body(  # pylint: disable=R0911
    *,
    count: int,
    article_title: str,
    sample_commenters: list[Any],
    distinct_commenter_count: int,
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

    if distinct_commenter_count <= 1:
        if usernames:
            return (
                f"{usernames[0]} left {count} comments on your article "
                f'"{article_title}".'
            )
        return f'{count} new comments on your article "{article_title}".'

    if distinct_commenter_count == 2:
        if len(usernames) >= 2:
            return (
                f"{usernames[0]} and {usernames[1]} commented on your article "
                f'"{article_title}".'
            )
        return f'2 people commented on your article "{article_title}".'

    if usernames:
        others = distinct_commenter_count - 1
        other_word = "other" if others == 1 else "others"
        return (
            f"{usernames[0]} and {others} {other_word} commented on your article "
            f'"{article_title}".'
        )

    return f'{count} new comments on your article "{article_title}".'


def _increment_unread_notification_count(user_id: int) -> None:
    User.objects.filter(id=user_id).update(
        unread_notifications_count=F("unread_notifications_count") + 1
    )


def _is_unread_aggregate_violation(exc: IntegrityError) -> bool:
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    diag = getattr(cause, "diag", None)
    if (
        diag
        and getattr(diag, "constraint_name", None)
        == UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT
    ):
        return True
    return UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT in str(exc)
