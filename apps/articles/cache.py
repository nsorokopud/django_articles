import logging
from typing import Iterable

from django.db import DatabaseError, OperationalError
from django_redis import get_redis_connection
from redis import RedisError

from .services import bulk_increment_article_view_counts
from .settings import ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE, ARTICLE_VIEW_SYNC_MAX_ITERATIONS


logger = logging.getLogger(__name__)


ARTICLE_VIEWED_BY_KEY = "articles:{article_id}:viewed_by:{viewer_id}"
ARTICLE_VIEWS_KEY = "articles:{id}:views"

VIEWED_ARTICLES_SET_KEY = "articles:viewed_to_sync"
VIEWED_ARTICLES_RETRY_SET_KEY = "articles:viewed_to_sync-retry"


def get_cached_article_views(article_id: int) -> int:
    redis_conn = get_redis_connection("default")
    article_key = ARTICLE_VIEWS_KEY.format(id=article_id)
    try:
        return int(redis_conn.get(article_key) or 0)
    except (ValueError, TypeError, RedisError) as e:
        logger.warning("Could not get cached views for article %s: %s", article_id, e)
        return 0


def increment_cached_article_views(article_id: int) -> None:
    redis_conn = get_redis_connection("default")
    article_key = ARTICLE_VIEWS_KEY.format(id=article_id)
    try:
        redis_conn.incr(article_key)
        redis_conn.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
    except RedisError as e:
        logger.error(
            "Redis error when incrementing views for article %s: %s", article_id, e
        )


def sync_article_views() -> None:
    redis_conn = get_redis_connection("default")

    _requeue_failed_view_syncs(redis_conn)

    for batch_index in range(ARTICLE_VIEW_SYNC_MAX_ITERATIONS):
        encoded_article_ids = redis_conn.spop(
            VIEWED_ARTICLES_SET_KEY, ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE
        )
        if not encoded_article_ids:
            logger.info(
                "No articles to sync; exiting on batch %d.",
                batch_index,
            )
            break

        article_ids = _decode_article_ids(encoded_article_ids)

        if not article_ids:
            logger.info("No valid article IDs in batch %s.", batch_index)
            continue

        _sync_article_batch(article_ids, batch_index, redis_conn)


def _requeue_failed_view_syncs(redis_conn) -> None:
    """Moves article IDs from retry set back to the main set for
    reprocessing."""
    retry_ids = redis_conn.smembers(VIEWED_ARTICLES_RETRY_SET_KEY)
    if retry_ids:
        redis_conn.sadd(VIEWED_ARTICLES_SET_KEY, *retry_ids)
        redis_conn.delete(VIEWED_ARTICLES_RETRY_SET_KEY)
        logger.info("Re-queued %d failed article view syncs", len(retry_ids))


def _decode_article_ids(encoded_ids: Iterable[bytes]) -> list[int]:
    article_ids = []
    for encoded_id in encoded_ids:
        try:
            article_id = int(encoded_id.decode("utf-8"))
            article_ids.append(article_id)
        except (UnicodeDecodeError, ValueError) as e:
            logger.warning("Skipping invalid article ID: %s (%s)", encoded_id, e)
    return article_ids


def _sync_article_batch(
    article_ids: Iterable[int], batch_index: int, redis_conn
) -> None:
    view_delta_values = _get_view_delta_values_from_cache(redis_conn, article_ids)
    view_deltas = _build_view_deltas_dict(article_ids, view_delta_values)

    if not view_deltas:
        logger.info(
            "No positive view deltas in batch %s for article IDs: %s",
            batch_index,
            article_ids,
        )
        _remove_synced_view_deltas_from_cache(redis_conn, article_ids)
        return

    try:
        bulk_increment_article_view_counts(view_deltas)
        logger.info(
            "Synced views for %d articles in batch %s.",
            len(view_deltas),
            batch_index,
        )
    except (DatabaseError, OperationalError) as e:
        logger.error("DB update failed. Re-queuing article IDs for retry. Error: %s", e)
        redis_conn.sadd(VIEWED_ARTICLES_RETRY_SET_KEY, *view_deltas.keys())
        return

    _remove_synced_view_deltas_from_cache(redis_conn, article_ids)


def _get_view_delta_values_from_cache(
    redis_conn, article_ids: Iterable[int]
) -> list[bytes]:
    try:
        with redis_conn.pipeline(transaction=True) as pipe:
            for article_id in article_ids:
                pipe.get(ARTICLE_VIEWS_KEY.format(id=article_id))
            delta_values = pipe.execute()
        return delta_values
    except RedisError as e:
        logger.error(
            "Redis error when getting views for articles %s: %s", article_ids, e
        )
        return []


def _build_view_deltas_dict(
    article_ids: Iterable[int], view_deltas: Iterable[bytes]
) -> dict[int, int]:
    result = {}
    for article_id, delta_value in zip(article_ids, view_deltas):
        try:
            delta = int(delta_value or 0)
            if delta > 0:
                result[article_id] = delta
        except (ValueError, TypeError) as e:
            logger.warning(
                "Invalid view delta value for key %s: %s",
                ARTICLE_VIEWS_KEY.format(id=article_id),
                e,
            )
    return result


def _remove_synced_view_deltas_from_cache(
    redis_conn, article_ids: Iterable[int]
) -> None:
    try:
        with redis_conn.pipeline(transaction=True) as pipe:
            for article_id in article_ids:
                pipe.delete(ARTICLE_VIEWS_KEY.format(id=article_id))
            pipe.execute()
    except RedisError as e:
        logger.warning("Redis cleanup failed for article IDs %s: %s", article_ids, e)
