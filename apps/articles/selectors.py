import logging
from typing import Optional, Sequence

from django.db.models import Count, Q
from django.db.models.query import QuerySet
from sql_util.utils import SubqueryAggregate
from taggit.models import Tag

from articles.models import Article, ArticleCategory, ArticleComment
from users.models import User


logger = logging.getLogger("default_logger")


def find_published_articles() -> QuerySet[Article]:
    return (
        Article.objects.filter(is_published=True)
        .select_related("category", "author", "author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .annotate(comments_count=Count("articlecomment", distinct=True))
        .order_by("-created_at")
    )


def find_articles_with_all_tags(
    tags: Sequence[Tag], queryset: Optional[QuerySet[Article]] = None
) -> QuerySet[Article]:
    """Returns articles that have all the specified tags. If no queryset
    is provided, uses the default published articles queryset. If no
    valid tags are provided, returns an empty queryset.
    """
    if queryset is None:
        queryset = find_published_articles()

    tag_ids = [tag.id for tag in tags if tag.id is not None]
    if not tag_ids:
        return queryset.none()

    return queryset.annotate(
        num_tags=Count("tags", filter=Q(tags__id__in=tag_ids), distinct=True)
    ).filter(num_tags=len(tag_ids))


def find_articles_by_query(
    q: str, queryset: Optional[QuerySet[Article]] = None
) -> QuerySet[Article]:
    if queryset is None:
        queryset = find_published_articles()

    return queryset.filter(
        Q(title__icontains=q)
        | Q(content__icontains=q)
        | Q(category__title__icontains=q)
        | Q(tags__name__icontains=q)
    ).distinct()


def find_article_comments_liked_by_user(article: Article, user: User) -> QuerySet[int]:
    """Returns ids of `ArticleComment` instances liked by the user"""
    return ArticleComment.objects.filter(
        article=article, users_that_liked=user
    ).values_list("id", flat=True)


def find_comments_to_article(article: Article) -> QuerySet[ArticleComment]:
    return (
        ArticleComment.objects.filter(article=article)
        .select_related("author", "author__profile")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
    )


def get_article_by_slug(article_slug: str) -> Article:
    return (
        Article.objects.select_related("author", "author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(slug=article_slug)
    )


def get_all_categories() -> QuerySet[ArticleCategory]:
    return ArticleCategory.objects.annotate(
        articles_count=SubqueryAggregate(
            "article__id", filter=Q(is_published=True), aggregate=Count
        )
    )


def get_all_tags() -> QuerySet[Tag]:
    return Tag.objects.all()


def get_comment_by_id(comment_id: int) -> ArticleComment:
    return ArticleComment.objects.get(id=comment_id)
