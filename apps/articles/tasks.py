import logging

from botocore.exceptions import BotoCoreError, ClientError
from celery.exceptions import SoftTimeLimitExceeded

from config.celery import app

from .cache import sync_article_views
from .services import delete_media_files_attached_to_article


logger = logging.getLogger("default_logger")


@app.task
def sync_article_views_task() -> None:
    sync_article_views()
    logger.info("Updated article view counts")


@app.task(
    bind=True,
    soft_time_limit=300,
    time_limit=310,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    retry_backoff=60,
    retry_jitter=False,
    autoretry_for=(OSError, BotoCoreError, ClientError, SoftTimeLimitExceeded),
)
def delete_article_inline_media_task(self, article_id: int, author_id: int) -> None:
    logger.info(
        "Deleting inline media for article %s by author %s. Task ID: %s.",
        article_id,
        author_id,
        self.request.id,
    )
    delete_media_files_attached_to_article(article_id, author_id)
