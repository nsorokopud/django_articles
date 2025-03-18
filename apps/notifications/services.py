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


def send_new_comment_notification(comment: ArticleComment, recipient: User) -> None:
    notification = create_new_comment_notification(comment, recipient)
    group_name = recipient.username
    _send_notification(notification, group_name)
    if recipient.profile.notification_emails_allowed:
        send_notification_email__task.delay(notification.id)


def send_new_article_notification(article: Article) -> None:
    subscribers = article.author.profile.subscribers.all()
    for subscriber in subscribers:
        notification = create_new_article_notification(article, subscriber)
        group_name = subscriber.username
        _send_notification(notification, group_name)
        if subscriber.profile.notification_emails_allowed:
            send_notification_email__task.delay(notification.id)


def _send_notification(notification: Notification, group_name: str):
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


def create_new_article_notification(article: Article, recipient: User) -> Notification:
    """Creates andd returns a notification about a new article."""
    notification = Notification.objects.create(
        type=Notification.Type.NEW_ARTICLE,
        title="New Article",
        message=f"New article from {article.author.username}: '{article.title}'",
        link=reverse("article-details", args=(article.slug,)),
        sender=article.author,
        recipient=recipient,
    )
    return notification


def create_new_comment_notification(comment: ArticleComment, recipient: User) -> Notification:
    """Creates andd returns a notification about a new comment on
    article.
    """
    notification = Notification.objects.create(
        type=Notification.Type.NEW_COMMENT,
        title="New Comment",
        message=f"New comment on your article from {comment.author.username}",
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
    email = EmailMultiAlternatives(notification.title, message, to=[notification.recipient.email])
    email.attach_alternative(message, "text/html")
    email.send()


def get_notification_by_id(notification_id: int) -> Notification:
    return Notification.objects.get(pk=notification_id)


def find_notifications_by_user(user: User) -> QuerySet[Notification]:
    """Returns a queryset of notifications addressed to the specified
    user.
    """
    return Notification.objects.filter(recipient__in=[user])


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
    return Notification.objects.filter(recipient=user, status=Notification.Status.UNREAD).count()
