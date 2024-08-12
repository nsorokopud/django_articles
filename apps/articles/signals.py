from django.db import transaction

from notifications.tasks import send_new_article_notification


def send_article_notification(sender, instance, created, **kwargs) -> None:
    if created:
        transaction.on_commit(lambda: send_new_article_notification.delay(instance.slug))
