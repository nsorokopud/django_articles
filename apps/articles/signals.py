from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ArticleComment
from .services.comments import (
    decrement_article_comments_count,
    increment_article_comments_count,
)


@receiver(post_save, sender=ArticleComment)
def article_comment_post_save(sender, instance, created, **kwargs):
    if created:
        increment_article_comments_count(article_id=instance.article_id)


@receiver(post_delete, sender=ArticleComment)
def article_comment_post_delete(sender, instance, **kwargs):
    decrement_article_comments_count(article_id=instance.article_id)
