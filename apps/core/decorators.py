from functools import wraps
from typing import Any, Callable

from django.views.decorators.cache import cache_page


def cache_page_for_anonymous(
    timeout: int,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        cached_view = cache_page(timeout)(view_func)

        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            return cached_view(request, *args, **kwargs)

        return _wrapped_view

    return decorator
