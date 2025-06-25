import logging
from functools import wraps
from typing import Any, Callable

from django_redis import get_redis_connection

from core.visitor_identifiers import get_visitor_id

from ..cache import ARTICLE_VIEWED_BY_KEY, increment_cached_article_views
from ..models import Article
from ..settings import ARTICLE_UNIQUE_VIEW_TIMEOUT


logger = logging.getLogger("default_logger")


def increment_article_view_counter(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """This decorator must be applied before caching decorators to
    ensure that the view counter is incremented before the response is
    cached."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs) -> Any:
        article_slug = kwargs.get("article_slug")
        if article_slug:
            try:
                article_id = Article.objects.values_list("id", flat=True).get(
                    slug=article_slug
                )
            except Article.DoesNotExist:
                logger.warning(
                    "Article not found for slug '%s'.",
                    article_slug,
                )
                return view_func(request, *args, **kwargs)

            cache_key = ARTICLE_VIEWED_BY_KEY.format(
                article_id=article_id, viewer_id=get_visitor_id(request)
            )
            redis_conn = get_redis_connection("default")
            if redis_conn.set(cache_key, "1", ex=ARTICLE_UNIQUE_VIEW_TIMEOUT, nx=True):
                increment_cached_article_views(article_id)
        return view_func(request, *args, **kwargs)

    return _wrapped_view
