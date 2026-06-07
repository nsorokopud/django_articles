import logging
from typing import Iterable

from django.conf import settings
from django.db import DatabaseError
from django_redis import get_redis_connection
from redis import RedisError

from ..services import bulk_increment_article_view_counts


logger = logging.getLogger(__name__)


ARTICLE_UNIQUE_VIEW_KEY = "articles:{article_id}:unique_view:{viewer_id}"
ARTICLE_UNSYNCED_VIEWS_KEY = "articles:{id}:views_delta"

VIEWED_ARTICLES_SET_KEY = "articles:viewed_to_sync"


REGISTER_ARTICLE_VIEW_LUA = """
local was_set = redis.call('SET', KEYS[1], '1', 'EX', ARGV[1], 'NX')
if not was_set then
    return 0
end

redis.call('INCR', KEYS[2])
redis.call('SADD', KEYS[3], ARGV[2])
return 1
"""


def get_cached_article_views(article_id: int) -> int:
    redis_conn = get_redis_connection("default")
    article_key = ARTICLE_UNSYNCED_VIEWS_KEY.format(id=article_id)
    try:
        return int(redis_conn.get(article_key) or 0)
    except (ValueError, TypeError, RedisError) as e:
        logger.warning("Could not get cached views for article %s: %s", article_id, e)
        return 0


def register_article_view(
    *,
    article_id: int,
    viewer_id: str,
    unique_view_timeout: int,
) -> bool:
    """Registers one unique view for an article within the timeout window.

    Returns True if a new unique view was counted.
    Returns False if the viewer had already viewed the article recently
    or if Redis failed.
    """
    redis_conn = get_redis_connection("default")
    unique_view_key = ARTICLE_UNIQUE_VIEW_KEY.format(
        article_id=article_id,
        viewer_id=viewer_id,
    )
    article_delta_key = ARTICLE_UNSYNCED_VIEWS_KEY.format(id=article_id)

    try:
        result = redis_conn.eval(
            REGISTER_ARTICLE_VIEW_LUA,
            3,
            unique_view_key,
            article_delta_key,
            VIEWED_ARTICLES_SET_KEY,
            unique_view_timeout,
            article_id,
        )
        return bool(result)
    except RedisError as e:
        logger.error(
            "Redis error while registering view for article %s and viewer %s: %s",
            article_id,
            viewer_id,
            e,
        )
        return False


def sync_article_views() -> None:
    redis_conn = get_redis_connection("default")

    for batch_index in range(settings.ARTICLES_VIEW_COUNT_SYNC_MAX_ITERATIONS):
        try:
            encoded_article_ids = redis_conn.spop(
                VIEWED_ARTICLES_SET_KEY,
                settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE,
            )
        except RedisError as e:
            logger.error("Redis error when popping article IDs to sync: %s", e)
            break

        if not encoded_article_ids:
            logger.info("No articles to sync; exiting on batch %d.", batch_index)
            break

        article_ids = _decode_article_ids(encoded_article_ids)
        if not article_ids:
            logger.info("No valid article IDs in batch %d.", batch_index)
            continue

        _sync_article_batch(article_ids, batch_index, redis_conn)


def _decode_article_ids(encoded_ids: Iterable[bytes]) -> list[int]:
    article_ids = []
    for encoded_id in encoded_ids:
        try:
            article_ids.append(int(encoded_id.decode("utf-8")))
        except (UnicodeDecodeError, ValueError) as e:
            logger.warning("Skipping invalid article ID: %s (%s)", encoded_id, e)
    return article_ids


def _sync_article_batch(
    article_ids: Iterable[int],
    batch_index: int,
    redis_conn,
) -> None:
    view_deltas = _claim_view_deltas(redis_conn, article_ids)

    if not view_deltas:
        logger.info(
            "No positive view deltas in batch %d for article IDs: %s",
            batch_index,
            list(article_ids),
        )
        return

    try:
        bulk_increment_article_view_counts(view_deltas)
        logger.info(
            "Synced views for %d articles in batch %d.",
            len(view_deltas),
            batch_index,
        )
    except DatabaseError as e:
        logger.error(
            "DB update failed. Restoring claimed article view deltas. Error: %s", e
        )
        restored = _restore_view_deltas(redis_conn, view_deltas)
        if not restored:
            logger.critical(
                "Failed to restore claimed article view deltas after DB failure. "
                "View deltas may be lost for article IDs: %s",
                list(view_deltas.keys()),
            )


def _claim_view_deltas(redis_conn, article_ids: Iterable[int]) -> dict[int, int]:
    """Atomically fetch and clear live deltas using GETDEL."""
    result: dict[int, int] = {}

    for article_id in article_ids:
        key = ARTICLE_UNSYNCED_VIEWS_KEY.format(id=article_id)
        try:
            raw_value = redis_conn.getdel(key)
        except RedisError as e:
            logger.error(
                "Redis error when claiming views for article %s: %s", article_id, e
            )
            try:
                redis_conn.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            except RedisError:
                logger.error(
                    "Could not re-queue article %s after failed delta claim.",
                    article_id,
                )
            continue

        try:
            delta = int(raw_value or 0)
        except (ValueError, TypeError) as e:
            logger.warning("Invalid view delta value for article %s: %s", article_id, e)
            continue

        if delta > 0:
            result[article_id] = delta

    return result


def _restore_view_deltas(redis_conn, view_deltas: dict[int, int]) -> bool:
    """Restore claimed deltas after DB failure."""
    if not view_deltas:
        return True

    try:
        with redis_conn.pipeline(transaction=True) as pipe:
            for article_id, delta in view_deltas.items():
                pipe.incrby(ARTICLE_UNSYNCED_VIEWS_KEY.format(id=article_id), delta)
                pipe.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            pipe.execute()
        return True
    except RedisError as e:
        logger.error("Redis error when restoring claimed view deltas: %s", e)
        return False
