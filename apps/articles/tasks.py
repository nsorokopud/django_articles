import logging

from botocore.exceptions import BotoCoreError, ClientError
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.db import DatabaseError
from django_redis.exceptions import ConnectionInterrupted
from redis import RedisError

from config.celery import app


logger = logging.getLogger(__name__)


ARTICLE_SYNC_VIEWS_LOCK_KEY = "articles_sync_views_lock"
ARTICLE_SYNC_VIEWS_LOCK_TIMEOUT_SECONDS = 300


@app.task(
    bind=True,
    autoretry_for=(DatabaseError, RedisError, ConnectionInterrupted),
    retry_backoff=60,
    retry_jitter=True,
    max_retries=3,
)
def sync_article_views_task(self) -> None:
    from .cache.view_counts import sync_article_views

    lock_value = self.request.id

    if not cache.add(
        ARTICLE_SYNC_VIEWS_LOCK_KEY,
        lock_value,
        timeout=ARTICLE_SYNC_VIEWS_LOCK_TIMEOUT_SECONDS,
    ):
        logger.info("Article view sync skipped: already running.")
        return

    try:
        sync_article_views()
        logger.info("Updated article view counts.")
    finally:
        if cache.get(ARTICLE_SYNC_VIEWS_LOCK_KEY) == lock_value:
            cache.delete(ARTICLE_SYNC_VIEWS_LOCK_KEY)


@app.task(
    bind=True,
    soft_time_limit=300,
    time_limit=310,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
    autoretry_for=(OSError, BotoCoreError, ClientError, SoftTimeLimitExceeded),
)
def delete_article_inline_media_task(self, article_id: int, author_id: int) -> None:
    from .services.media import delete_media_files_attached_to_article

    logger.info(
        "Deleting inline media for article %s by author %s. Task ID: %s.",
        article_id,
        author_id,
        self.request.id,
    )
    delete_media_files_attached_to_article(article_id, author_id)
