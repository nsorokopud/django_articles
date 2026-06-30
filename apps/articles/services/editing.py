import logging
from typing import Optional

from django.db import IntegrityError, transaction
from django.template.defaultfilters import slugify
from nanoid import generate

from core.db import get_constraint_name
from users.models import User

from ..cache.slug import invalidate_article_slug_id
from ..constants import DEFAULT_DRAFT_ARTICLE_TITLE
from ..models import (
    ARTICLE_SLUG_MAX_LENGTH,
    ARTICLE_SLUG_UNIQUE_CONSTRAINT_NAME,
    Article,
    ArticleStatus,
)
from ..search_utils import extract_searchable_text
from .media import (
    delete_article_preview_image_file,
    sync_article_inline_media_references,
)
from .sanitization import sanitize_article_html


ARTICLE_SLUG_SUFFIX_LENGTH = 8
MAX_SLUG_RETRY_ATTEMPTS = 5

logger = logging.getLogger(__name__)


@transaction.atomic
def get_or_create_empty_draft(*, author: User) -> Article:
    User.objects.select_for_update().only("id").get(pk=author.pk)

    existing_draft = (
        Article.objects.select_for_update()
        .filter(
            author_id=author.pk,
            status=ArticleStatus.DRAFT,
            title=DEFAULT_DRAFT_ARTICLE_TITLE,
            preview_text="",
            content="",
            content_text="",
        )
        .order_by("-created_at", "-id")
        .first()
    )

    if existing_draft:
        return existing_draft

    return _create_empty_draft(author=author)


@transaction.atomic
def save_article(
    *,
    article: Article,
    author: User | None = None,
    restore_rejected_to_draft: bool = True,
) -> Article:
    is_new = article.pk is None

    original_article = None
    if is_new:
        if author is None:
            raise ValueError("author is required when creating an article")
        article.author = author
    else:
        original_article = (
            Article.objects.select_for_update()
            .only("title", "slug", "status", "preview_image")
            .get(pk=article.pk)
        )

    if original_article is not None and original_article.status in {
        ArticleStatus.PUBLISHED,
        ArticleStatus.PENDING_REVIEW,
    }:
        raise ValueError("published or pending-review articles cannot be edited")

    old_slug = original_article.slug if original_article is not None else None
    old_preview_image_name = (
        original_article.preview_image.name
        if original_article is not None and original_article.preview_image
        else ""
    )

    article.content = sanitize_article_html(
        article.content, article_id=article.id, author_id=article.author_id
    )
    article.content_text = extract_searchable_text(article.content)

    # Editing a rejected article reopens it as a draft.
    if (
        original_article is not None
        and original_article.status == ArticleStatus.REJECTED
        and restore_rejected_to_draft
    ):
        article.status = ArticleStatus.DRAFT
        article.review_note = ""
        article.reviewed_at = None
        article.reviewed_by = None

    if _should_regenerate_slug(article, original_article):
        _save_with_unique_slug(article)
    else:
        article.save()

    new_preview_image_name = article.preview_image.name if article.preview_image else ""
    sync_article_inline_media_references(article=article)

    if old_slug and old_slug != article.slug:
        transaction.on_commit(lambda: invalidate_article_slug_id(article_slug=old_slug))

    if old_preview_image_name and old_preview_image_name != new_preview_image_name:
        transaction.on_commit(
            lambda: delete_article_preview_image_file(old_preview_image_name)
        )

    return article


@transaction.atomic
def delete_article(*, article_id: int) -> None:
    article = Article.objects.select_for_update().get(id=article_id)

    if article.status in {
        ArticleStatus.PUBLISHED,
        ArticleStatus.PENDING_REVIEW,
    }:
        raise ValueError("published or pending-review articles cannot be deleted")

    article_slug = article.slug
    author_id = article.author_id
    preview_image_name = article.preview_image.name

    article.delete()

    def after_commit() -> None:
        from ..tasks import delete_article_media_task

        invalidate_article_slug_id(article_slug=article_slug)
        delete_article_media_task.delay(
            article_id=article_id,
            author_id=author_id,
            preview_image_name=preview_image_name,
        )

    transaction.on_commit(after_commit)


def _create_empty_draft(*, author: User) -> Article:
    article = Article(
        author=author,
        title=DEFAULT_DRAFT_ARTICLE_TITLE,
        preview_text="",
        content="",
        content_text="",
        status=ArticleStatus.DRAFT,
    )
    _save_with_unique_slug(article)
    return article


def _save_with_unique_slug(article: Article) -> None:
    for attempt in range(MAX_SLUG_RETRY_ATTEMPTS):
        article.slug = _build_article_slug_candidate(
            article.title, use_suffix=(attempt > 0)
        )

        try:
            with transaction.atomic():
                article.save()
            return
        except IntegrityError as exc:
            if get_constraint_name(exc) != ARTICLE_SLUG_UNIQUE_CONSTRAINT_NAME:
                raise

            if attempt == MAX_SLUG_RETRY_ATTEMPTS - 1:
                raise


def _build_article_slug_candidate(title: str, *, use_suffix: bool) -> str:
    base = slugify(title).strip("-") or "article"

    if not use_suffix:
        return base[:ARTICLE_SLUG_MAX_LENGTH].rstrip("-") or "article"

    suffix = generate(size=ARTICLE_SLUG_SUFFIX_LENGTH)
    max_base_length = ARTICLE_SLUG_MAX_LENGTH - len(suffix) - 1
    base = base[:max_base_length].rstrip("-") or "article"

    return f"{base}-{suffix}"


def _should_regenerate_slug(
    article: Article, original_article: Optional[Article]
) -> bool:
    if not article.slug:
        return True

    if original_article is None:
        return False

    title_changed = article.title != original_article.title
    slug_can_change = original_article.status in {
        ArticleStatus.DRAFT,
        ArticleStatus.REJECTED,
    }

    return title_changed and slug_can_change
