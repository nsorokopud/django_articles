from django.db import connection, transaction
from django.utils import timezone

from notifications.services.articles import (
    notify_article_published,
    notify_article_rejected,
    notify_article_unpublished,
)
from users.models import User
from users.services.users import advance_latest_article_publish_sequence

from ..models import ARTICLE_PUBLISH_SEQUENCE_NAME, Article, ArticleStatus


@transaction.atomic
def submit_article_for_review(*, article_id: int) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status == ArticleStatus.PENDING_REVIEW:
        return article

    if article.status not in (ArticleStatus.DRAFT, ArticleStatus.REJECTED):
        raise ValueError("only draft or rejected articles can be submitted for review")

    article.status = ArticleStatus.PENDING_REVIEW
    article.save(update_fields=["status"])

    return article


@transaction.atomic
def withdraw_article_from_review(*, article_id: int) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status == ArticleStatus.DRAFT:
        return article

    if article.status != ArticleStatus.PENDING_REVIEW:
        raise ValueError("only articles pending review can be withdrawn from review")

    article.status = ArticleStatus.DRAFT
    article.save(update_fields=["status"])

    return article


@transaction.atomic
def publish_article(*, article_id: int, actor: User | None = None) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status == ArticleStatus.PUBLISHED:
        return article

    if article.status != ArticleStatus.PENDING_REVIEW:
        raise ValueError("only articles pending review can be published")

    seq = get_next_article_publish_sequence_value()
    article.status = ArticleStatus.PUBLISHED
    article.published_at = timezone.now()
    article.publish_sequence = seq

    article.review_note = ""
    article.reviewed_at = None
    article.reviewed_by = None

    article.save(
        update_fields=[
            "status",
            "published_at",
            "publish_sequence",
            "review_note",
            "reviewed_at",
            "reviewed_by",
        ]
    )

    advance_latest_article_publish_sequence(
        user_id=article.author_id, publish_sequence=seq
    )

    if actor is None or actor.id != article.author_id:
        notify_article_published(
            recipient_id=article.author_id,
            article_id=article.id,
            article_slug=article.slug,
            article_title=article.title,
            actor_id=actor.id if actor else None,
            publish_sequence=article.publish_sequence,
        )

    return article


@transaction.atomic
def unpublish_article(*, article_id: int, actor: User | None = None) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.PUBLISHED:
        return article

    unpublished_at = timezone.now()

    article.status = ArticleStatus.DRAFT
    article.published_at = None
    article.publish_sequence = None
    article.save(update_fields=["status", "published_at", "publish_sequence"])

    if actor is not None and actor.id != article.author_id:
        notify_article_unpublished(
            recipient_id=article.author_id,
            article_id=article.id,
            article_slug=article.slug,
            article_title=article.title,
            actor_id=actor.id,
            unpublished_at_ts=unpublished_at.isoformat(),
        )

    return article


@transaction.atomic
def reject_article(
    *,
    article_id: int,
    reviewer: User | None = None,
    reason: str = "",
) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.PENDING_REVIEW:
        raise ValueError("only articles pending review can be rejected")

    if article.status == ArticleStatus.REJECTED and not reason and reviewer is None:
        return article

    article.status = ArticleStatus.REJECTED
    article.published_at = None
    article.publish_sequence = None
    article.review_note = reason.strip()
    article.reviewed_at = timezone.now()
    article.reviewed_by = reviewer

    article.save(
        update_fields=[
            "status",
            "published_at",
            "publish_sequence",
            "review_note",
            "reviewed_at",
            "reviewed_by",
        ]
    )

    notify_article_rejected(
        recipient_id=article.author_id,
        article_id=article.id,
        article_slug=article.slug,
        article_title=article.title,
        review_note=article.review_note,
        reviewer_id=reviewer.id if reviewer else None,
        reviewed_at_ts=article.reviewed_at.isoformat() if article.reviewed_at else None,
    )

    return article


@transaction.atomic
def restore_article_to_draft(*, article_id: int) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status == ArticleStatus.DRAFT:
        return article

    if article.status != ArticleStatus.REJECTED:
        raise ValueError("only rejected articles can be restored to draft")

    article.status = ArticleStatus.DRAFT
    article.save(update_fields=["status"])
    return article


def get_next_article_publish_sequence_value() -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT nextval('{ARTICLE_PUBLISH_SEQUENCE_NAME}')")
        return int(cursor.fetchone()[0])
