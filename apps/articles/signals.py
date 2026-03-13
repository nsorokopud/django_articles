from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Article
from .tasks import delete_article_inline_media_task


@receiver(post_delete, sender=Article)
def delete_article_media_files(sender, instance, **kwargs) -> None:
    transaction.on_commit(
        lambda: delete_article_inline_media_task.delay(instance.id, instance.author.id)
    )
