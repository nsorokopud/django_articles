from datetime import timedelta

from celery.schedules import crontab

from ..env import env
from .cache import REDIS_CELERY_BROKER_URL, REDIS_CELERY_RESULT_URL


CELERY_BROKER_URL = REDIS_CELERY_BROKER_URL
CELERY_RESULT_BACKEND = REDIS_CELERY_RESULT_URL
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = env.bool(
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP", default=True
)


CELERY_BEAT_SCHEDULE = {
    "articles.cleanup-unused-media": {
        "task": "articles.tasks.cleanup_unused_article_inline_media_task",
        "schedule": timedelta(hours=1),
    },
    "articles.sync-view-counts": {
        "task": "articles.tasks.sync_article_views_task",
        "schedule": timedelta(minutes=5),
    },
    "articles.sync-article-likes-counts": {
        "task": "articles.tasks.sync_article_likes_count_task",
        "schedule": timedelta(hours=1),
    },
    "articles.sync-article-comment-counts": {
        "task": "articles.tasks.sync_article_comments_count_task",
        "schedule": timedelta(hours=1),
    },
    "articles.sync-comment-likes-counts": {
        "task": "articles.tasks.sync_comment_likes_count_task",
        "schedule": timedelta(hours=1),
    },
    "notifications.cleanup-old-read": {
        "task": "notifications.tasks_retention.cleanup_old_read_notifications_task",
        "schedule": timedelta(hours=1),
    },
    "notifications.sync-unread-counts": {
        "task": "notifications.tasks.sync_unread_notification_counts_task",
        "schedule": crontab(minute=0, hour="*/6"),  # every 6 hours
    },
    "users.delete-expired-pending-email-changes": {
        "task": "users.tasks.delete_expired_pending_email_changes_task",
        "schedule": timedelta(hours=1),
    },
}
