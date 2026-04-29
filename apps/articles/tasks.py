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
ARTICLE_SYNC_VIEWS_LOCK_TIMEOUT_SECONDS = 10 * 60  # 10 min


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
    soft_time_limit=300,
    time_limit=310,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
    autoretry_for=(OSError, BotoCoreError, ClientError, SoftTimeLimitExceeded),
)
def delete_article_media_task(
    article_id: int,
    author_id: int,
    preview_image_name: str = "",
) -> None:
    from .services.media import delete_article_media_files

    delete_article_media_files(
        article_id=article_id,
        author_id=author_id,
        preview_image_name=preview_image_name,
    )
