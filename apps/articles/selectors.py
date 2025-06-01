from typing import Iterable, Optional

from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from sql_util.utils import SubqueryAggregate
from taggit.models import Tag

from articles.models import Article, ArticleCategory, ArticleComment
from users.models import User


def find_published_articles() -> QuerySet[Article]:
    return (
        Article.objects.filter(is_published=True)
        .select_related("category")
        .select_related("author")
        .select_related("author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .annotate(comments_count=Count("articlecomment", distinct=True))
        .order_by("-created_at")
    )


def find_articles_of_category(category_slug: str) -> QuerySet[Article]:
    return find_published_articles().filter(category__slug=category_slug)


def find_articles_with_tags(
    tags: Iterable[str], queryset: Optional[QuerySet[Article]] = None
) -> QuerySet[Article]:
    if queryset is None:
        queryset = find_published_articles()

    for tag in tags:
        queryset = queryset.filter(tags__name=tag)
    return queryset


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


def find_article_comments_liked_by_user(article_slug: str, user: User) -> QuerySet[int]:
    """Returns ids of `ArticleComment` instances liked by the user"""
    return ArticleComment.objects.filter(
        article__slug=article_slug, users_that_liked=user
    ).values_list("id", flat=True)


def find_comments_to_article(article_slug: str) -> QuerySet[ArticleComment]:
    return (
        ArticleComment.objects.filter(article__slug=article_slug)
        .select_related("author")
        .select_related("author__profile")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
    )


def get_article_by_id(article_id: int) -> Article:
    return (
        Article.objects.select_related("author")
        .select_related("author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(id=article_id)
    )


def get_article_by_slug(article_slug: str) -> Article:
    return (
        Article.objects.select_related("author")
        .select_related("author__profile")
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


def get_all_tags():
    return Tag.objects.all()


def get_all_users_that_liked_article(article_slug: str) -> QuerySet[User]:
    article = get_object_or_404(Article, slug=article_slug)
    return article.users_that_liked.all()


def get_comment_by_id(comment_id: int) -> ArticleComment:
    return ArticleComment.objects.get(id=comment_id)
