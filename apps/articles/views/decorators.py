import logging
from functools import wraps
from typing import Any, Callable

from django.conf import settings

from core.visitor_identifiers import get_visitor_id

from ..cache.slug import get_cached_article_id_by_slug
from ..cache.view_counts import register_article_view


logger = logging.getLogger(__name__)


def increment_article_view_counter(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """Apply before caching decorators so unique views are counted even
    when the response is served from cache.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs) -> Any:
        article_slug = kwargs.get("article_slug")
        article_id = None

        if article_slug:
            article_id = get_cached_article_id_by_slug(article_slug)

        if article_id is not None:
            register_article_view(
                article_id=article_id,
                viewer_id=get_visitor_id(request),
                unique_view_timeout=settings.ARTICLES_UNIQUE_VIEW_WINDOW_SECONDS,
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view
