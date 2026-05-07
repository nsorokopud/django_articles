from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ArticleComment
from .services.comments import (
    decrement_article_comments_count,
)


@receiver(post_delete, sender=ArticleComment)
def article_comment_post_delete(sender, instance, **kwargs):
    decrement_article_comments_count(article_id=instance.article_id)
