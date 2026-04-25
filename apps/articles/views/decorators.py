import logging
from functools import wraps
from typing import Any, Callable

from core.visitor_identifiers import get_visitor_id

from ..cache.view_counts import register_article_view
from ..models import Article
from ..settings import ARTICLE_UNIQUE_VIEW_TIMEOUT


logger = logging.getLogger(__name__)


def increment_article_view_counter(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """Apply before caching decorators so unique views are counted even
    when the response is served from cache.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs) -> Any:
        article_slug = kwargs.get("article_slug")
        if article_slug:
            try:
                article_id = Article.objects.values_list("id", flat=True).get(
                    slug=article_slug
                )
            except Article.DoesNotExist:
                logger.warning("Article not found for slug '%s'.", article_slug)
            else:
                register_article_view(
                    article_id=article_id,
                    viewer_id=get_visitor_id(request),
                    unique_view_timeout=ARTICLE_UNIQUE_VIEW_TIMEOUT,
                )

        return view_func(request, *args, **kwargs)

    return _wrapped_view
