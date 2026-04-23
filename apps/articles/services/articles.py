import logging
from typing import Optional

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Case, F, IntegerField, Value, When
from django.template.defaultfilters import slugify
from nanoid import generate

from users.models import User

from ..models import Article, ArticleStatus
from ..search_utils import extract_searchable_text
from .sanitization import sanitize_article_html


MAX_SLUG_RETRY_ATTEMPTS = 5

logger = logging.getLogger(__name__)


@transaction.atomic
def create_empty_draft(*, author: User) -> Article:
    article = Article(
        author=author,
        title=settings.DEFAULT_DRAFT_ARTICLE_TITLE,
        preview_text="",
        content="",
        status=ArticleStatus.DRAFT,
    )

    _save_with_unique_slug(article)
    return article


@transaction.atomic
def save_article(
    *,
    article: Article,
    author: User | None = None,
    restore_rejected_to_draft: bool = True,
) -> Article:
    is_new = article.pk is None

    previous_article = None
    if is_new:
        if author is None:
            raise ValueError("author is required when creating an article")
        article.author = author
    else:
        previous_article = (
            Article.objects.select_for_update()
            .only("title", "slug", "status")
            .get(pk=article.pk)
        )

    article.content = sanitize_article_html(article.content)
    article.content_text = extract_searchable_text(article.content)

    if _should_regenerate_slug(article, previous_article):
        _save_with_unique_slug(article)
    else:
        article.save()

    # Business rule: editing a rejected article reopens it as a draft.
    if (
        previous_article is not None
        and previous_article.status == ArticleStatus.REJECTED
        and restore_rejected_to_draft
    ):
        article.status = ArticleStatus.DRAFT
        article.save(update_fields=["status"])

    return article


def _save_with_unique_slug(article: Article) -> None:
    for attempt in range(MAX_SLUG_RETRY_ATTEMPTS):
        article.slug = _build_article_slug_candidate(
            article.title,
            use_suffix=(attempt > 0),
        )
        try:
            with transaction.atomic():
                article.save()
            return
        except IntegrityError:
            if attempt == MAX_SLUG_RETRY_ATTEMPTS - 1:
                raise


def _build_article_slug_candidate(title: str, *, use_suffix: bool) -> str:
    base = slugify(title).strip("-") or "article"
    if not use_suffix:
        return base
    return f"{base}-{generate(size=8)}"


def _should_regenerate_slug(
    article: Article, previous_article: Optional[Article]
) -> bool:
    if not article.slug:
        return True

    if previous_article is None:
        return False

    title_changed = article.title != previous_article.title
    was_unpublished = previous_article.status != ArticleStatus.PUBLISHED

    return title_changed and was_unpublished


def bulk_increment_article_view_counts(view_deltas: dict[int, int]) -> None:
    """Increment article view counts in the DB using a single bulk
    UPDATE with CASE.

    view_deltas: a dictionary mapping article IDs to numbers of views
    to increment with.
    """
    if not view_deltas:
        logger.warning("No deltas to process for bulk update.")
        return

    when_clauses = [
        When(pk=article_id, then=F("views_count") + Value(view_delta))
        for article_id, view_delta in sorted(view_deltas.items())
    ]

    try:
        with transaction.atomic():
            Article.objects.filter(pk__in=view_deltas).update(
                views_count=Case(
                    *when_clauses,
                    default=F("views_count"),
                    output_field=IntegerField(),
                )
            )
    except DatabaseError:
        logger.exception("Failed to bulk update view counts.")
        raise
