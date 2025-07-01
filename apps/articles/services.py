import logging
import os
import posixpath
from typing import BinaryIO, List, Optional
from uuid import uuid4

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.db import DatabaseError, connection, transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify
from django.utils.text import get_valid_filename

from core.exceptions import MediaSaveError
from users.models import User

from .models import Article, ArticleCategory, ArticleComment


logger = logging.getLogger("default_logger")


@transaction.atomic
def create_article(
    *,
    title: str,
    author: User,
    preview_text: str,
    content: str,
    category: Optional[ArticleCategory] = None,
    tags: Optional[List] = None,
    preview_image: Optional[str] = None,
) -> Article:
    article = Article(
        title=title,
        category=category,
        author=author,
        preview_text=preview_text,
        preview_image=preview_image,
        content=content,
        is_published=True,
    )
    article.slug = _generate_unique_article_slug(title)
    article.save()
    if tags is not None:
        article.tags.add(*tags)
    return article


def increment_article_views_counter(article: Article) -> int:
    article.views_count = F("views_count") + 1
    article.save(update_fields=("views_count",))
    article.refresh_from_db()
    return article.views_count


def bulk_increment_article_view_counts(view_deltas: dict[int, int]) -> None:
    """Increment article view counts in the DB using a single bulk
    UPDATE with CASE.

    view_deltas: a dictionary mapping article IDs to numbers of views
    to increment with.
    """
    if not view_deltas:
        logger.warning("No deltas to process for bulk update.")
        return

    case_statements = []
    case_params = []
    where_placeholders = []
    where_params = []

    for article_id, view_delta in sorted(view_deltas.items()):
        case_statements.append("WHEN id = %s THEN views_count + %s")
        case_params.extend([article_id, view_delta])
        where_placeholders.append("%s")
        where_params.append(article_id)

    case_sql = "CASE " + " ".join(case_statements) + " END"
    where_clause = f"id IN ({', '.join(where_placeholders)})"

    sql_template = """
        UPDATE articles_article
        SET views_count = {case_sql}
        WHERE {where_clause}
    """
    sql = sql_template.format(case_sql=case_sql, where_clause=where_clause)
    params = case_params + where_params

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
    except DatabaseError as e:
        logger.exception("Failed to bulk update view counts: %s", e)


def toggle_article_like(article_slug: str, user_id: int) -> int:
    article = get_object_or_404(Article, slug=article_slug)
    try:
        user = article.users_that_liked.get(id=user_id)
        article.users_that_liked.remove(user)
    except User.DoesNotExist:
        user = get_object_or_404(User, id=user_id)
        article.users_that_liked.add(user)
    likes_count = (
        Article.objects.annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(slug=article_slug)
        .likes_count
    )
    return likes_count


def toggle_comment_like(comment_id: int, user_id: int) -> Optional[int]:
    comment = get_object_or_404(ArticleComment, id=comment_id)
    try:
        user = comment.users_that_liked.get(id=user_id)
        comment.users_that_liked.remove(user)
    except User.DoesNotExist:
        user = User.objects.get(id=user_id)
        comment.users_that_liked.add(user)
    likes_count = (
        ArticleComment.objects.annotate(
            likes_count=Count("users_that_liked", distinct=True)
        )
        .get(id=comment_id)
        .likes_count
    )
    return likes_count


def _generate_unique_article_slug(article_title: str):
    """Returns a unique slug for the specified article title. If an
    article with the specified title already exists, the corresponding
    slug is returned. Otherwise the next available unique slug is
    returned.
    """
    try:
        article = Article.objects.get(title=article_title)
        return article.slug
    except Article.DoesNotExist:
        slug = slugify(article_title)
        unique_slug = slug

        number = 1
        while Article.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{slug}-{number}"
            number += 1

        return unique_slug


def save_media_file_attached_to_article(
    file: BinaryIO, article: Article
) -> tuple[str, str]:
    file_path = _build_safe_file_path(file, article)

    try:
        file_path = default_storage.save(file_path, file)
    except (
        OSError,
        SuspiciousFileOperation,
        S3UploadFailedError,
        ClientError,
    ) as e:
        logger.exception(
            "Failed to save file for article %s: %s (%s)",
            article.id,
            file_path,
            type(e).__name__,
        )
        raise MediaSaveError("Could not save the uploaded file.") from e

    return file_path, article.get_absolute_url()


def _build_safe_file_path(file: BinaryIO, article: Article) -> str:
    base_name, extension = os.path.splitext(file.name)
    safe_base_name = get_valid_filename(base_name)
    filename = f"{safe_base_name}_{uuid4().hex}.{extension.lower()}"
    author_dir = get_valid_filename(article.author.get_username())
    directory = posixpath.join("articles", "uploads", author_dir, str(article.pk))
    return posixpath.join(directory, filename)


def delete_media_files_attached_to_article(article: Article) -> None:
    article_dir = os.path.join(
        "articles", "uploads", article.author.username, str(article.id)
    )
    if default_storage.exists(article_dir):
        for file in default_storage.listdir(article_dir)[1]:
            default_storage.delete(os.path.join(article_dir, file))
        default_storage.delete(article_dir)
