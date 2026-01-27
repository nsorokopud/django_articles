import asyncio
import json
import logging
from random import randint
from typing import Optional, Sequence

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django_redis import get_redis_connection
from redis import RedisError

from .models import User
from .settings import SUBSCRIBERS_COUNT_CACHE_TIMEOUT


logger = logging.getLogger(__name__)


def get_cached_subscribers_count(author: User) -> int:
    cache_key = get_subscribers_count_cache_key(author.id)
    count = cache.get(cache_key)
    if count is None:
        count = author.subscribers.count()
        cache.set(cache_key, count, timeout=SUBSCRIBERS_COUNT_CACHE_TIMEOUT)
    return int(count)


async def get_cached_subscribed_to_authors(user_id: int) -> Optional[list[int]]:
    redis = get_redis_connection("default")
    cache_key = get_subscribed_to_authors_cache_key(user_id)

    try:
        raw = await sync_to_async(redis.get, thread_sensitive=False)(cache_key)
        if raw is None:
            return None

        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")

        data = json.loads(raw)
        if not isinstance(data, list):
            raise TypeError("cached payload is not a list")

        return [int(a_id) for a_id in data]
    except (json.JSONDecodeError, ValueError, TypeError):
        try:
            await sync_to_async(redis.delete, thread_sensitive=False)(cache_key)
        except RedisError:
            logger.debug(
                "Failed to delete corrupted cache key '%s'.", cache_key, exc_info=True
            )
        logger.warning(
            "Corrupted JSON in cache `%s` for user %s; key evicted.",
            cache_key,
            user_id,
        )
        return None
    except RedisError as e:
        logger.warning(
            "Failed to get cached subscribed-to authors for user %s: %s", user_id, e
        )
        return None
    except asyncio.CancelledError:  # pylint: disable=W0706
        raise
    except Exception:  # pylint: disable=W0718
        logger.exception(
            "Unexpected error reading subscribed-to authors cache for user %s.", user_id
        )
        return None


async def cache_subscribed_to_authors(user_id: int, author_ids: Sequence[int]) -> bool:
    redis = get_redis_connection("default")
    cache_timeout = max(
        1, settings.SUBSCRIBED_TO_AUTHORS_CACHE_TIMEOUT + randint(-60, 60)  # nosec B311
    )

    try:
        payload = [int(a) for a in author_ids]
        value = json.dumps(payload, separators=(",", ":"))

        await sync_to_async(redis.setex, thread_sensitive=False)(
            get_subscribed_to_authors_cache_key(user_id),
            cache_timeout,
            value,
        )
        logger.debug(
            "Cached %d subscribed-to authors for user %s.", len(payload), user_id
        )
        return True
    except (TypeError, ValueError):
        logger.warning("Invalid payload; not caching for user %s.", user_id)
        return False
    except RedisError as e:
        logger.warning(
            "Failed to cache subscribed-to authors for user %s: %s.", user_id, e
        )
        return False
    except asyncio.CancelledError:  # pylint: disable=W0706
        raise
    except Exception:  # pylint: disable=W0718
        logger.exception(
            "Unexpected error caching subscribed-to authors for user %s.", user_id
        )
        return False


def get_subscribers_count_cache_key(user_id: int) -> str:
    return f"users:subscribers_count:{user_id}"


def get_subscribed_to_authors_cache_key(user_id: int) -> str:
    return f"users:{user_id}:subscribed_to_authors:v1"
