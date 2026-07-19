import logging
from typing import Iterable

from django.conf import settings
from django.db import DatabaseError
from django_redis import get_redis_connection
from redis import Redis, RedisError

from ..services.view_counts import bulk_increment_article_view_counts


logger = logging.getLogger(__name__)

UNIQUE_VIEW_KEY = "articles:{article_id}:unique_view:{viewer_id}"
VIEW_DELTA_KEY = "articles:{article_id}:views_delta"
ARTICLES_PENDING_VIEW_SYNC_KEY = "articles:viewed_to_sync"

REGISTER_VIEW_LUA = """
local unique_view_key, delta_key, pending_articles_key = KEYS[1], KEYS[2], KEYS[3]
local timeout, article_id = ARGV[1], ARGV[2]

local is_new_view = redis.call('SET', unique_view_key, '1', 'EX', timeout, 'NX')
if not is_new_view then
    return 0
end

redis.call('INCR', delta_key)
redis.call('SADD', pending_articles_key, article_id)
return 1
"""


def get_cached_article_views(article_id: int) -> int:
    redis = get_redis_connection("default")

    try:
        raw_value = redis.get(_view_delta_key(article_id))
    except RedisError:
        logger.exception("Could not get cached views for article %s", article_id)
        return 0

    try:
        return int(raw_value or 0)
    except (TypeError, ValueError):
        logger.warning("Invalid delta (%r) for article %s", raw_value, article_id)
        return 0


def register_article_view(
    *, article_id: int, viewer_id: str, unique_view_timeout: int
) -> bool:
    """Count one view per viewer within the configured time window."""
    redis = get_redis_connection("default")

    try:
        return bool(
            redis.eval(
                REGISTER_VIEW_LUA,
                3,
                UNIQUE_VIEW_KEY.format(article_id=article_id, viewer_id=viewer_id),
                _view_delta_key(article_id),
                ARTICLES_PENDING_VIEW_SYNC_KEY,
                unique_view_timeout,
                article_id,
            )
        )
    except RedisError:
        logger.exception(
            "Could not register view (article %s, viewer %s)", article_id, viewer_id
        )
        return False


def sync_article_views() -> None:
    """Flush Redis view deltas to DB.

    DB failures restore claimed deltas, but an abrupt worker crash after
    GETDEL can still lose claimed views, so counts are approximate.
    """
    redis = get_redis_connection("default")
    batch_size = settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE

    for batch_index in range(settings.ARTICLES_VIEW_COUNT_SYNC_MAX_ITERATIONS):
        try:
            raw_ids = redis.spop(ARTICLES_PENDING_VIEW_SYNC_KEY, batch_size)
        except RedisError:
            logger.exception("Could not pop article IDs to sync")
            break

        if not raw_ids:
            logger.debug("No articles to sync; exiting on batch %d", batch_index)
            break

        article_ids = _parse_article_ids(raw_ids)

        if article_ids:
            _sync_article_batch(redis, article_ids, batch_index)
        else:
            logger.info("No valid article IDs in batch %d", batch_index)


def _parse_article_ids(raw_ids: Iterable[bytes | str]) -> list[int]:
    article_ids = []

    for raw_id in raw_ids:
        try:
            article_ids.append(int(raw_id))
        except (TypeError, ValueError):
            logger.warning("Skipping invalid article ID: %r", raw_id)

    return article_ids


def _sync_article_batch(
    redis: Redis, article_ids: Iterable[int], batch_index: int
) -> None:
    view_deltas = _claim_view_deltas(redis, article_ids)

    if not view_deltas:
        logger.debug("No positive view deltas in batch %d", batch_index)
        return

    try:
        bulk_increment_article_view_counts(view_deltas)
    except DatabaseError:
        if not _restore_claimed_view_deltas(redis, view_deltas):
            logger.error("View deltas may be lost for articles: %s", list(view_deltas))
        return

    logger.info(
        "Synced views for %d articles in batch %d", len(view_deltas), batch_index
    )


def _claim_view_deltas(redis: Redis, article_ids: Iterable[int]) -> dict[int, int]:
    view_deltas = {}

    for article_id in article_ids:
        try:
            raw_delta = redis.getdel(_view_delta_key(article_id))
        except RedisError:
            logger.exception("Could not claim views for article %s", article_id)
            _requeue_article(redis, article_id)
            continue

        try:
            delta = int(raw_delta or 0)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            logger.warning("Invalid delta (%r) for article %s", raw_delta, article_id)
            continue

        if delta > 0:
            view_deltas[article_id] = delta

    return view_deltas


def _requeue_article(redis: Redis, article_id: int) -> None:
    try:
        redis.sadd(ARTICLES_PENDING_VIEW_SYNC_KEY, article_id)
    except RedisError:
        logger.exception("Could not requeue article %s", article_id)


def _restore_claimed_view_deltas(redis: Redis, view_deltas: dict[int, int]) -> bool:
    if not view_deltas:
        return True

    try:
        with redis.pipeline(transaction=True) as pipe:
            for article_id, delta in view_deltas.items():
                pipe.incrby(_view_delta_key(article_id), delta)
                pipe.sadd(ARTICLES_PENDING_VIEW_SYNC_KEY, article_id)

            pipe.execute()

        return True
    except RedisError:
        logger.exception("Could not restore claimed view deltas")
        return False


def _view_delta_key(article_id: int) -> str:
    return VIEW_DELTA_KEY.format(article_id=article_id)
