import logging

from config.celery import app

from .cache import sync_article_views


logger = logging.getLogger("default_logger")


@app.task
def sync_article_views_task() -> None:
    sync_article_views()
    logger.info("Updated article view counts")
