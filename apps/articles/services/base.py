import logging
from typing import List, Optional

from django.db import DatabaseError, connection, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify

from users.models import User

from ..models import Article, ArticleCategory, ArticleComment


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
    article.slug = generate_unique_article_slug(title)
    article.save()
    if tags is not None:
        article.tags.add(*tags)
    return article


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


def generate_unique_article_slug(article_title: str):
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
