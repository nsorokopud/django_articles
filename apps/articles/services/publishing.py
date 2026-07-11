from datetime import datetime
from html import unescape

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from notifications.services.articles import (
    notify_article_published,
    notify_article_rejected,
    notify_article_unpublished,
)
from users.models import User

from ..cache.slug import invalidate_article_slug_id
from ..constants import DEFAULT_DRAFT_ARTICLE_TITLE
from ..models import Article, ArticleStatus


@transaction.atomic
def submit_article_for_review(*, article_id: int) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.DRAFT:
        raise ValueError("only draft articles can be submitted for review")

    _validate_article_ready(article, action="submission for review")

    article.status = ArticleStatus.PENDING_REVIEW
    article.review_note = ""
    article.reviewed_at = None
    article.reviewed_by = None
    article.save(update_fields=["status", "review_note", "reviewed_at", "reviewed_by"])

    _invalidate_article_slug_id_cache_on_commit(article)

    return article


@transaction.atomic
def withdraw_article_from_review(*, article_id: int) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.PENDING_REVIEW:
        raise ValueError("only articles pending review can be withdrawn from review")

    article.status = ArticleStatus.DRAFT
    article.save(update_fields=["status"])
    return article


@transaction.atomic
def publish_article(*, article_id: int, reviewer: User | None = None) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.PENDING_REVIEW:
        raise ValueError("only articles pending review can be published")

    _validate_article_ready(article, action="publishing")

    now = timezone.now()

    article.status = ArticleStatus.PUBLISHED
    article.published_at = now
    article.review_note = ""
    article.reviewed_at = now
    article.reviewed_by = reviewer

    article.save(
        update_fields=[
            "status",
            "published_at",
            "review_note",
            "reviewed_at",
            "reviewed_by",
        ]
    )

    _notify_article_published_on_commit(
        article=article, actor=reviewer, published_at=article.published_at
    )

    return article


@transaction.atomic
def unpublish_article(*, article_id: int, actor: User | None = None) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.PUBLISHED:
        raise ValueError("only published articles can be unpublished")

    unpublished_at = timezone.now()

    article.status = ArticleStatus.DRAFT
    article.published_at = None
    article.save(update_fields=["status", "published_at"])

    _invalidate_article_slug_id_cache_on_commit(article)
    _notify_article_unpublished_on_commit(
        article=article, actor=actor, unpublished_at=unpublished_at
    )

    return article


@transaction.atomic
def reject_article(
    *, article_id: int, reviewer: User | None = None, reason: str = ""
) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.PENDING_REVIEW:
        raise ValueError("only articles pending review can be rejected")

    cleaned_reason = reason.strip()
    if not cleaned_reason:
        raise ValueError("rejection reason is required")

    article.status = ArticleStatus.REJECTED
    article.published_at = None
    article.review_note = cleaned_reason
    article.reviewed_at = timezone.now()
    article.reviewed_by = reviewer

    article.save(
        update_fields=[
            "status",
            "published_at",
            "review_note",
            "reviewed_at",
            "reviewed_by",
        ]
    )

    _invalidate_article_slug_id_cache_on_commit(article)
    _notify_article_rejected_on_commit(article=article, reviewer=reviewer)

    return article


def _validate_article_ready(article: Article, *, action: str) -> None:
    if (
        not _normalize_article_text(article.title)
        or article.title == DEFAULT_DRAFT_ARTICLE_TITLE
    ):
        raise ValueError(f"Title is required before {action}.")

    if not _normalize_article_text(article.preview_text):
        raise ValueError(f"Preview text is required before {action}.")

    if not _has_meaningful_html_content(article.content):
        raise ValueError(f"Content is required before {action}.")


def _normalize_article_text(value: str | None) -> str:
    return (value or "").strip()


def _has_meaningful_html_content(html: str | None) -> bool:
    text = unescape(strip_tags(html or ""))
    normalized = text.replace("\xa0", " ").strip()
    return bool(normalized)


def _invalidate_article_slug_id_cache_on_commit(article: Article) -> None:
    article_slug = article.slug

    transaction.on_commit(lambda: invalidate_article_slug_id(article_slug=article_slug))


def _notify_article_published_on_commit(
    *, article: Article, actor: User | None, published_at: datetime
) -> None:
    article_id = article.id
    author_id = article.author_id
    article_slug = article.slug
    article_title = article.title
    actor_id = actor.id if actor else None

    if actor_id == author_id:
        return

    transaction.on_commit(
        lambda: notify_article_published(
            recipient_id=author_id,
            article_id=article_id,
            article_slug=article_slug,
            article_title=article_title,
            actor_id=actor_id,
            published_at=published_at,
        )
    )


def _notify_article_unpublished_on_commit(
    *, article: Article, actor: User | None, unpublished_at: datetime
) -> None:
    if actor is None or actor.id == article.author_id:
        return

    article_id = article.id
    author_id = article.author_id
    article_slug = article.slug
    article_title = article.title
    actor_id = actor.id
    unpublished_at_ts = unpublished_at.isoformat()

    transaction.on_commit(
        lambda: notify_article_unpublished(
            recipient_id=author_id,
            article_id=article_id,
            article_slug=article_slug,
            article_title=article_title,
            actor_id=actor_id,
            unpublished_at_ts=unpublished_at_ts,
        )
    )


def _notify_article_rejected_on_commit(
    *, article: Article, reviewer: User | None
) -> None:
    article_id = article.id
    author_id = article.author_id
    article_slug = article.slug
    article_title = article.title
    review_note = article.review_note
    reviewer_id = reviewer.id if reviewer else None
    reviewed_at_ts = article.reviewed_at.isoformat() if article.reviewed_at else None

    transaction.on_commit(
        lambda: notify_article_rejected(
            recipient_id=author_id,
            article_id=article_id,
            article_slug=article_slug,
            article_title=article_title,
            review_note=review_note,
            reviewer_id=reviewer_id,
            reviewed_at_ts=reviewed_at_ts,
        )
    )
