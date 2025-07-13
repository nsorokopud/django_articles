import logging
from typing import Optional

from django.db import DatabaseError, connection, transaction
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify
from nanoid import generate

from ..models import Article, ArticleComment


logger = logging.getLogger("default_logger")


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
    return toggle_like(article, user_id)


def toggle_comment_like(comment_id: int, user_id: int) -> Optional[int]:
    comment = get_object_or_404(ArticleComment, id=comment_id)
    return toggle_like(comment, user_id)


@transaction.atomic
def toggle_like(obj: Article | ArticleComment, user_id: int) -> int:
    if obj.users_that_liked.filter(id=user_id).exists():
        obj.users_that_liked.remove(user_id)
    else:
        obj.users_that_liked.add(user_id)

    return obj.users_that_liked.count()


def generate_unique_article_slug(article_title: str) -> str:
    base = slugify(article_title)
    slug = base
    while Article.objects.filter(slug=slug).exists():
        slug = f"{base}-{generate(size=6)}"
    return slug
