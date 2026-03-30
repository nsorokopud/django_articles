from django.db import connection, transaction
from django.utils import timezone

from users.models import User
from users.services.users import advance_latest_article_publish_sequence

from ..models import Article, ArticleStatus


@transaction.atomic
def publish_article(*, article_id: int) -> Article:
    a = Article.objects.select_for_update().get(id=article_id)

    if a.status == ArticleStatus.PUBLISHED:
        return a

    if a.status != ArticleStatus.DRAFT:
        raise ValueError("only draft articles can be published")

    seq = get_next_article_publish_sequence_value()
    a.status = ArticleStatus.PUBLISHED
    a.published_at = timezone.now()
    a.publish_sequence = seq

    a.review_note = ""
    a.reviewed_at = None
    a.reviewed_by = None

    a.save(
        update_fields=[
            "status",
            "published_at",
            "publish_sequence",
            "review_note",
            "reviewed_at",
            "reviewed_by",
        ]
    )

    advance_latest_article_publish_sequence(user_id=a.author_id, publish_sequence=seq)
    return a


@transaction.atomic
def unpublish_article(*, article_id: int) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status != ArticleStatus.PUBLISHED:
        return article

    article.status = ArticleStatus.DRAFT
    article.published_at = None
    article.publish_sequence = None

    article.save(update_fields=["status", "published_at", "publish_sequence"])
    return article


@transaction.atomic
def reject_article(
    *,
    article_id: int,
    reviewer: User | None = None,
    reason: str = "",
) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status == ArticleStatus.PUBLISHED:
        raise ValueError("published articles cannot be rejected")

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
    return article


@transaction.atomic
def restore_article_to_draft(*, article_id: int) -> Article:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status == ArticleStatus.DRAFT:
        return article

    if article.status != ArticleStatus.REJECTED:
        raise ValueError("only rejected articles can be restored to draft")

    article.status = ArticleStatus.DRAFT
    article.reviewed_at = None
    article.reviewed_by = None
    article.save(update_fields=["status", "reviewed_at", "reviewed_by"])
    return article


def get_next_article_publish_sequence_value() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('article_publish_seq')")
        return int(cursor.fetchone()[0])
