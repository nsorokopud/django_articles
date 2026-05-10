from django.urls import reverse

from ..models import Notification
from .creation import create_system_notification
from .dispatch import dispatch_notification_after_commit


def notify_article_published(
    *,
    recipient_id: int,
    article_id: int,
    article_slug: str,
    article_title: str,
    actor_id: int | None = None,
    publish_sequence: int | None = None,
) -> None:
    notification, created = create_system_notification(
        recipient_id=recipient_id,
        sender_id=actor_id,
        level=Notification.Level.SUCCESS,  # type: ignore[arg-type]
        title="Article published",
        body=f'Your article "{article_title}" has been published.',
        payload={
            "kind": "article_published",
            "articleId": article_id,
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "url": reverse("article-details", kwargs={"article_slug": article_slug}),
            "publishSequence": publish_sequence,
        },
        dedupe_key=(
            f"article-published:{article_id}:{publish_sequence}"
            if publish_sequence is not None
            else f"article-published:{article_id}:{article_slug}"
        ),
    )

    dispatch_notification_after_commit(
        notification_id=notification.id,
        notification_type=notification.notification_type,
        is_new_unread=created,
    )


def notify_article_rejected(
    *,
    recipient_id: int,
    article_id: int,
    article_slug: str,
    article_title: str,
    review_note: str,
    reviewer_id: int | None = None,
    reviewed_at_ts: str | None = None,
) -> None:
    body = f'Your article "{article_title}" was rejected.'
    if review_note:
        body += f" Review note: {review_note}"

    notification, created = create_system_notification(
        recipient_id=recipient_id,
        sender_id=reviewer_id,
        level=Notification.Level.WARNING,  # type: ignore[arg-type]
        title="Article rejected",
        body=body,
        payload={
            "kind": "article_rejected",
            "articleId": article_id,
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "reviewNote": review_note,
            "url": reverse("article-update", kwargs={"pk": article_id}),
            "reviewedAt": reviewed_at_ts,
        },
        dedupe_key=(
            f"article-rejected:{article_id}:{reviewed_at_ts}"
            if reviewed_at_ts
            else f"article-rejected:{article_id}:{article_slug}"
        ),
    )

    dispatch_notification_after_commit(
        notification_id=notification.id,
        notification_type=notification.notification_type,
        is_new_unread=created,
    )


def notify_article_unpublished(
    *,
    recipient_id: int,
    article_id: int,
    article_slug: str,
    article_title: str,
    actor_id: int | None = None,
    unpublished_at_ts: str | None = None,
) -> None:
    notification, created = create_system_notification(
        recipient_id=recipient_id,
        sender_id=actor_id,
        level=Notification.Level.WARNING,  # type: ignore[arg-type]
        title="Article unpublished",
        body=f'Your article "{article_title}" was unpublished.',
        payload={
            "kind": "article_unpublished",
            "articleId": article_id,
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "url": reverse("article-update", kwargs={"pk": article_id}),
            "unpublishedAt": unpublished_at_ts,
        },
        dedupe_key=(
            f"article-unpublished:{article_id}:{unpublished_at_ts}"
            if unpublished_at_ts
            else f"article-unpublished:{article_id}:{article_slug}"
        ),
    )

    dispatch_notification_after_commit(
        notification_id=notification.id,
        notification_type=notification.notification_type,
        is_new_unread=created,
    )
