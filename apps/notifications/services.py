from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.urls import reverse

from articles.models import Article, ArticleComment
from .models import Notification


def send_new_comment_notification(comment: ArticleComment, recipient: User) -> None:
    notification = create_new_comment_notification(comment, recipient)
    group_name = recipient.username
    _send_notification(notification, group_name)


def send_new_article_notification(article: Article) -> None:
    subscribers = article.author.profile.subscribers.all()
    for subscriber in subscribers:
        notification = create_new_article_notification(article, subscriber)
        group_name = subscriber.username
        _send_notification(notification, group_name)


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
        }
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


def find_notifications_by_user(user: User) -> QuerySet[Notification]:
    """Returns a queryset of notifications addressed to the specified
    user.
    """
    return Notification.objects.filter(recipient__in=[user])
