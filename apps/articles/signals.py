from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from notifications.tasks import (
    send_new_article_notification,
    send_new_comment_notification,
)

from .models import Article, ArticleComment
from .services import delete_media_files_attached_to_article


@receiver(post_save, sender=Article)
def send_article_notification(sender, instance, created, **kwargs) -> None:
    if created and not kwargs.get("raw", False):
        transaction.on_commit(
            lambda: send_new_article_notification.delay(instance.slug)
        )


@receiver(post_save, sender=ArticleComment)
def send_comment_notification(sender, instance, created, **kwargs) -> None:
    if created and not kwargs.get("raw", False):
        send_new_comment_notification.delay(instance.id, instance.article.author.id)


@receiver(post_delete, sender=Article)
def delete_article_media_files(sender, instance, **kwargs) -> None:
    delete_media_files_attached_to_article(instance)
