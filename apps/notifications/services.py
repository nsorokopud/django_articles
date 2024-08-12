from django.contrib.auth.models import User
from django.urls import reverse

from articles.models import Article, ArticleComment
from .models import Notification


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
