import logging

from django.db import IntegrityError, transaction

from notifications.services.creation import create_new_comment_notification
from notifications.services.dispatch import dispatch_notification_after_commit
from users.models import User

from ..models import Article, ArticleComment


logger = logging.getLogger(__name__)


def create_article_comment(
    *, article: Article, user: User, text: str
) -> ArticleComment:
    """Creates an article comment and schedules related notification dispatch."""
    comment = ArticleComment.objects.create(
        article=article,
        author=user,
        text=text,
    )

    try:
        with transaction.atomic():
            notification_result = create_new_comment_notification(
                comment_id=comment.id,
                comment_author_id=user.id,
                comment_author_username=user.username,
                article_id=article.id,
                article_author_id=article.author_id,
                article_slug=article.slug,
                article_title=article.title,
            )

            if notification_result is not None:
                notification, created = notification_result
                dispatch_notification_after_commit(
                    notification_id=notification.id,
                    notification_type=notification.notification_type,
                    is_new_unread=created,
                )
    except (IntegrityError, RuntimeError):
        logger.exception(
            "Failed to create notification for article comment %s "
            "(article_id=%s, user_id=%s)",
            comment.id,
            article.id,
            user.id,
        )

    return comment
