from django.core.cache import cache

from .models import User
from .settings import SUBSCRIBERS_COUNT_CACHE_TIMEOUT


def get_cached_subscribers_count(author: User) -> int:
    cache_key = get_subscribers_count_cache_key(author.id)
    count = cache.get(cache_key)
    if count is None:
        count = author.subscribers.count()
        cache.set(cache_key, count, timeout=SUBSCRIBERS_COUNT_CACHE_TIMEOUT)
    return int(count)


def get_subscribers_count_cache_key(user_id: int) -> str:
    return f"users:subscribers_count:{user_id}"
