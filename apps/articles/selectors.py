from typing import Optional, Sequence

from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.query import QuerySet
from taggit.models import Tag

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from users.models import User


ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT = 20


def find_published_articles() -> QuerySet[Article]:
    return (
        Article.objects.filter(status=ArticleStatus.PUBLISHED)
        .select_related("category", "author", "author__profile")
        .prefetch_related("tags")
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

    query = SearchQuery(q, config="english", search_type="websearch")

    return (
        queryset.annotate(
            rank=SearchRank(
                "search_vector", query, cover_density=True, normalization=32
            ),
            title_similarity=TrigramSimilarity("title", q),
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
        .filter(Q(search_vector=query) | Q(title__trigram_similar=q))
        .order_by(
            "-exact_title_match",
            "-title_contains_match",
            "-rank",
            "-title_similarity",
            "-publish_sequence",
            "-id",
        )
    )


def find_article_comments_liked_by_user(
    comment_ids: Sequence[int], user: User
) -> QuerySet[int]:
    return ArticleComment.objects.filter(
        id__in=comment_ids,
        users_that_liked=user,
    ).values_list("id", flat=True)


def find_comments_to_article(article: Article) -> QuerySet[ArticleComment]:
    return (
        ArticleComment.objects.filter(article=article)
        .select_related("author", "author__profile")
        .order_by("-created_at", "-id")
    )


def get_published_article_by_slug(article_slug: str) -> Article:
    return (
        Article.objects.filter(status=ArticleStatus.PUBLISHED)
        .select_related("author", "author__profile", "category")
        .prefetch_related("tags")
        .get(slug=article_slug)
    )


def get_article_for_author_by_slug(*, article_slug: str, author_id: int) -> Article:
    return (
        Article.objects.select_related("author", "author__profile", "category")
        .prefetch_related("tags")
        .get(slug=article_slug, author_id=author_id)
    )


def find_article_filter_categories() -> QuerySet[ArticleCategory]:
    return (
        ArticleCategory.objects.filter(article__status=ArticleStatus.PUBLISHED)
        .distinct()
        .order_by("title")
    )


def find_article_filter_tags() -> QuerySet[Tag]:
    return (
        Tag.objects.filter(article__status=ArticleStatus.PUBLISHED)
        .distinct()
        .order_by("name")
    )


def find_article_filter_authors() -> QuerySet[User]:
    return (
        User.objects.filter(article__status=ArticleStatus.PUBLISHED)
        .distinct()
        .order_by("username")
    )


def find_article_filter_tag_suggestions(q: str) -> QuerySet[Tag]:
    queryset = find_article_filter_tags()

    q = (q or "").strip()
    if q:
        queryset = queryset.filter(name__icontains=q)

    return queryset[:ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT]


def find_article_filter_author_suggestions(q: str) -> QuerySet[User]:
    queryset = find_article_filter_authors()

    q = (q or "").strip()
    if q:
        queryset = queryset.filter(username__icontains=q)

    return queryset[:ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT]


def get_comment_by_id(comment_id: int) -> ArticleComment:
    return ArticleComment.objects.get(id=comment_id)
