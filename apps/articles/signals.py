from django.db import transaction

from notifications.tasks import (
    send_new_article_notification,
    send_new_comment_notification,
)

from .services import delete_media_files_attached_to_article


def send_article_notification(sender, instance, created, **kwargs) -> None:
    if created and not kwargs.get("raw", False):
        transaction.on_commit(lambda: send_new_article_notification.delay(instance.slug))


def send_comment_notification(sender, instance, created, **kwargs) -> None:
    if created and not kwargs.get("raw", False):
        send_new_comment_notification.delay(instance.id, instance.article.author.id)


def delete_article_media_files(sender, instance, **kwargs) -> None:
    delete_media_files_attached_to_article(instance)
