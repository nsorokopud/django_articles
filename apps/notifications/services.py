import logging
from typing import Any, Iterable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.mail import EmailMultiAlternatives
from django.db.models.query import QuerySet
from django.template.loader import render_to_string
from django.urls import reverse

from articles.models import Article, ArticleComment
from config.settings import DOMAIN_NAME, SCHEME
from users.models import User

from .models import Notification
from .tasks import send_notification_email as send_notification_email__task


logger = logging.getLogger("default_logger")


def send_new_comment_notification(comment: ArticleComment, recipient: User) -> None:
    notification = create_new_comment_notification(comment, recipient)
    group_name = recipient.username
    _send_notification(notification, group_name)
    if recipient.profile.notification_emails_allowed:
        send_notification_email__task.delay(notification.id)


def send_new_article_notification(article: Article) -> None:
    subscribers = article.author.profile.subscribers.all()
    subscriber_count = subscribers.count()
    logger.info(
        "Found %d subscribers for article with ID=%d", subscriber_count, article.id
    )
    if subscribers.count() > 0:
        notifications = bulk_create_new_article_notifications(article, subscribers)
        for notification in notifications:
            group_name = notification.recipient.username
            _send_notification(notification, group_name)
            if notification.recipient.profile.notification_emails_allowed:
                send_notification_email__task.delay(notification.id)
        logger.info(
            (
                "Initiated sending of %d `New article` notifications about article"
                "with ID=%d"
            ),
            len(notifications),
            article.id,
        )


def _send_notification(notification: Notification, group_name: str):
    logger.info(
        "Attempting to send notification with ID=%d to group %s via channels",
        notification.id,
        group_name,
    )
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "send_notification",
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "link": notification.link,
            "timestamp": notification.created_at.isoformat(),
        },
    )
    logger.info(
        "Successfully sent notification with ID=%d to group %s via channels",
        notification.id,
        group_name,
    )


def bulk_create_new_article_notifications(
    article: Article, recipients: Iterable[User]
) -> list[Notification]:
    notifications = []
    message = _render_notification_message(
        "notifications/new_article_notification.html",
        {"article_author": article.author.username, "article_title": article.title},
    )
    for user in recipients:
        notifications.append(
            Notification(
                type=Notification.Type.NEW_ARTICLE,
                title="New Article",
                message=message,
                link=reverse("article-details", args=(article.slug,)),
                sender=article.author,
                recipient=user,
            )
        )
    created_notifications = Notification.objects.bulk_create(
        notifications, batch_size=500
    )
    logger.info(
        "Created %d `New article` notifications about article with ID=%d",
        len(created_notifications),
        article.id,
    )
    return created_notifications


def _render_notification_message(template_name: str, context: dict[str, Any]) -> str:
    """Renders a notification message from a template."""
    return render_to_string(template_name, context).strip("\n").replace("\n", " ")


def create_new_comment_notification(
    comment: ArticleComment, recipient: User
) -> Notification:
    """Creates and returns a notification about a new comment on
    article.
    """
    message = _render_notification_message(
        "notifications/new_comment_notification.html",
        {
            "article_title": comment.article.title,
            "comment_author": comment.author.username,
        },
    )
    notification = Notification.objects.create(
        type=Notification.Type.NEW_COMMENT,
        title="New Comment",
        message=message,
        link=reverse("article-details", args=(comment.article.slug,)),
        sender=comment.author,
        recipient=recipient,
    )
    return notification


def send_notification_email(notification: Notification) -> None:
    message = render_to_string(
        "notifications/email.html",
        {
            "message": notification.message,
            "url": f"{SCHEME}://{DOMAIN_NAME}{notification.link}",
        },
    )
    email = EmailMultiAlternatives(
        notification.title, message, to=[notification.recipient.email]
    )
    email.attach_alternative(message, "text/html")
    email.send()


def get_notification_by_id(notification_id: int) -> Notification:
    return Notification.objects.get(pk=notification_id)


def find_notifications_by_user(user: User) -> QuerySet[Notification]:
    """Returns a queryset of notifications addressed to the specified
    user.
    """
    return Notification.objects.filter(recipient=user)


def mark_notification_as_read(notification: Notification) -> None:
    """Changes the status of the notification to 'read'."""
    notification.status = Notification.Status.READ
    notification.save()


def delete_notification(notification: Notification) -> None:
    notification.delete()


def get_unread_notifications_count_by_user(user: User) -> int:
    """Returns the total count of unread notifications addressed to the
    specified user.
    """
    return Notification.objects.filter(
        recipient=user, status=Notification.Status.UNREAD
    ).count()
