from django.conf import settings
from django.core.cache import cache

from ..models import Article, ArticleStatus


ARTICLE_SLUG_ID_CACHE_KEY = "articles:slug:{slug}:id"


def get_cached_article_id_by_slug(article_slug: str) -> int | None:
    cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug=article_slug)

    article_id = cache.get(cache_key)
    if article_id is not None:
        try:
            return int(article_id)
        except (TypeError, ValueError):
            cache.delete(cache_key)

    article_id = (
        Article.objects.filter(slug=article_slug, status=ArticleStatus.PUBLISHED)
        .values_list("id", flat=True)
        .first()
    )

    if article_id is None:
        return None

    cache.set(cache_key, article_id, settings.ARTICLES_SLUG_ID_CACHE_TIMEOUT_SECONDS)
    return int(article_id)


def invalidate_article_slug_id(*, article_slug: str) -> None:
    cache.delete(ARTICLE_SLUG_ID_CACHE_KEY.format(slug=article_slug))
