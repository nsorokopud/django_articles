import logging

from botocore.exceptions import BotoCoreError, ClientError
from celery.exceptions import SoftTimeLimitExceeded
from django.db import DatabaseError
from django_redis.exceptions import ConnectionInterrupted
from redis.exceptions import RedisError

from config.celery import app
from core.cache_locks import cache_lock


logger = logging.getLogger(__name__)


ARTICLE_SYNC_VIEWS_LOCK_KEY = "articles_sync_views_lock"
ARTICLE_SYNC_LIKES_LOCK_KEY = "articles_sync_likes_lock"
COMMENT_SYNC_LIKES_LOCK_KEY = "comments_sync_likes_lock"
ARTICLE_SYNC_COMMENT_COUNTS_LOCK_KEY = "articles_sync_comment_counts_lock"

ARTICLE_SYNC_VIEWS_LOCK_TIMEOUT_SECONDS = 10 * 60  # 10 min
SYNC_LIKES_LOCK_TIMEOUT_SECONDS = 30 * 60  # 30 minutes
ARTICLE_SYNC_COMMENT_COUNTS_LOCK_TIMEOUT_SECONDS = 30 * 60  # 30 min

ARTICLE_MEDIA_CLEANUP_LOCK_KEY = "articles_media_cleanup_lock"
ARTICLE_MEDIA_CLEANUP_LOCK_TIMEOUT_SECONDS = 60 * 60  # 1 hour
ARTICLE_MEDIA_CLEANUP_BATCH_SIZE = 500
ARTICLE_MEDIA_CLEANUP_MAX_BATCHES = 10


@app.task(
    bind=True,
    autoretry_for=(DatabaseError, RedisError, ConnectionInterrupted),
    retry_backoff=60,
    retry_jitter=True,
    max_retries=3,
)
def sync_article_views_task(self) -> None:
    from .cache.view_counts import sync_article_views

    lock_value = self.request.id or None

    with cache_lock(
        lock_key=ARTICLE_SYNC_VIEWS_LOCK_KEY,
        lock_value=lock_value,
        timeout=ARTICLE_SYNC_VIEWS_LOCK_TIMEOUT_SECONDS,
    ) as lock:
        if not lock.acquired:
            logger.info("Article view sync skipped: already running.")
            return

        sync_article_views()
        logger.info("Updated article view counts.")


@app.task(
    bind=True,
    autoretry_for=(DatabaseError, RedisError, ConnectionInterrupted),
    retry_backoff=60,
    retry_jitter=True,
    max_retries=3,
)
def sync_article_likes_count_task(self) -> None:
    from .services.likes import sync_article_likes_count

    lock_value = self.request.id or None

    with cache_lock(
        lock_key=ARTICLE_SYNC_LIKES_LOCK_KEY,
        lock_value=lock_value,
        timeout=SYNC_LIKES_LOCK_TIMEOUT_SECONDS,
    ) as lock:
        if not lock.acquired:
            logger.info("Article likes sync skipped: already running.")
            return

        sync_article_likes_count()
        logger.info("Synced article likes counts.")


@app.task(
    bind=True,
    autoretry_for=(DatabaseError, RedisError, ConnectionInterrupted),
    retry_backoff=60,
    retry_jitter=True,
    max_retries=3,
)
def sync_comment_likes_count_task(self) -> None:
    from .services.likes import sync_comment_likes_count

    lock_value = self.request.id or None

    with cache_lock(
        lock_key=COMMENT_SYNC_LIKES_LOCK_KEY,
        lock_value=lock_value,
        timeout=SYNC_LIKES_LOCK_TIMEOUT_SECONDS,
    ) as lock:
        if not lock.acquired:
            logger.info("Comment likes sync skipped: already running.")
            return

        sync_comment_likes_count()
        logger.info("Synced comment likes counts.")


@app.task(
    bind=True,
    autoretry_for=(DatabaseError, RedisError, ConnectionInterrupted),
    retry_backoff=60,
    retry_jitter=True,
    max_retries=3,
)
def sync_article_comments_count_task(self, *, batch_size: int = 1000) -> None:
    from .services.comments import sync_article_comments_count

    lock_value = self.request.id or None

    with cache_lock(
        lock_key=ARTICLE_SYNC_COMMENT_COUNTS_LOCK_KEY,
        lock_value=lock_value,
        timeout=ARTICLE_SYNC_COMMENT_COUNTS_LOCK_TIMEOUT_SECONDS,
    ) as lock:
        if not lock.acquired:
            logger.info("Article comments count sync skipped: already running.")
            return

        sync_article_comments_count(batch_size=batch_size)
        logger.info("Synced article comments counts.")


@app.task(
    bind=True,
    soft_time_limit=300,  # 5 min
    time_limit=330,  # 5.5 min
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(
        DatabaseError,
        OSError,
        BotoCoreError,
        ClientError,
        SoftTimeLimitExceeded,
    ),
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
)
def cleanup_unused_article_inline_media_task(
    self,
    batch_size=ARTICLE_MEDIA_CLEANUP_BATCH_SIZE,
    max_batches=ARTICLE_MEDIA_CLEANUP_MAX_BATCHES,
) -> None:
    from .services.media import cleanup_unused_article_inline_media

    lock_value = self.request.id or None

    with cache_lock(
        lock_key=ARTICLE_MEDIA_CLEANUP_LOCK_KEY,
        lock_value=lock_value,
        timeout=ARTICLE_MEDIA_CLEANUP_LOCK_TIMEOUT_SECONDS,
    ) as lock:
        if not lock.acquired:
            logger.info("Article media cleanup skipped: already running.")
            return

        total_deleted = 0

        for _ in range(max_batches):
            deleted_count = cleanup_unused_article_inline_media(batch_size=batch_size)
            total_deleted += deleted_count

            if deleted_count == 0:
                break

        logger.info("Cleaned up %s unused article media files.", total_deleted)
