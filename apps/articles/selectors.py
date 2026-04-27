import logging
from typing import Optional, Sequence

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.query import QuerySet
from sql_util.utils import SubqueryAggregate
from taggit.models import Tag

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from users.models import User


logger = logging.getLogger(__name__)


def find_published_articles() -> QuerySet[Article]:
    return (
        Article.objects.filter(status=ArticleStatus.PUBLISHED)
        .select_related("category", "author", "author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .annotate(comments_count=Count("articlecomment", distinct=True))
        .order_by("-publish_sequence", "-id")
    )


def find_subscription_feed_articles(user: User) -> QuerySet[Article]:
    return (
        find_published_articles()
        .filter(author__subscriptions_received__subscriber=user)
        .distinct()
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


def find_articles_by_author(author: User) -> QuerySet[Article]:
    return (
        Article.objects.filter(author=author)
        .select_related("category", "author", "author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .annotate(comments_count=Count("articlecomment", distinct=True))
        .order_by("-modified_at", "-id")
    )


def find_articles_by_query(
    q: str, queryset: Optional[QuerySet[Article]] = None
) -> QuerySet[Article]:
    if queryset is None:
        queryset = find_published_articles()

    q = (q or "").strip()
    if not q:
        return queryset

    query = SearchQuery(q, config="english")

    base_ids = queryset.values("id")

    matching_ids = (
        Article.objects.filter(id__in=base_ids)
        .filter(
            Q(search_vector=query)
            | Q(title__icontains=q)
            | Q(category__title__icontains=q)
            | Q(tags__name__icontains=q)
        )
        .values("id")
        .distinct()
    )

    return (
        queryset.filter(id__in=matching_ids)
        .annotate(
            rank=SearchRank("search_vector", query),
            exact_title_match=Case(
                When(title__iexact=q, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            title_contains_match=Case(
                When(title__icontains=q, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .order_by(
            "-exact_title_match",
            "-title_contains_match",
            "-rank",
            "-publish_sequence",
            "-id",
        )
    )


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
        .order_by("-created_at", "-id")
    )


def get_article_by_slug(article_slug: str) -> Article:
    return (
        Article.objects.select_related("author", "author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(slug=article_slug)
    )


def get_published_article_by_slug(article_slug: str) -> Article:
    return (
        Article.objects.filter(status=ArticleStatus.PUBLISHED)
        .select_related("author", "author__profile", "category")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(slug=article_slug)
    )


def get_article_for_author_by_slug(*, article_slug: str, author_id: int) -> Article:
    return (
        Article.objects.select_related("author", "author__profile", "category")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(slug=article_slug, author_id=author_id)
    )


def get_all_categories() -> QuerySet[ArticleCategory]:
    return ArticleCategory.objects.annotate(
        articles_count=SubqueryAggregate(
            "article__id", filter=Q(status=ArticleStatus.PUBLISHED), aggregate=Count
        )
    )


def get_all_tags() -> QuerySet[Tag]:
    return Tag.objects.all()


def get_comment_by_id(comment_id: int) -> ArticleComment:
    return ArticleComment.objects.get(id=comment_id)
