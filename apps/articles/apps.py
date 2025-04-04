from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class ArticlesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "articles"

    def ready(self):
        from .models import Article, ArticleComment
        from .signals import (
            delete_article_media_files,
            send_article_notification,
            send_comment_notification,
        )

        post_save.connect(send_article_notification, sender=Article)
        post_save.connect(send_comment_notification, sender=ArticleComment)

        post_delete.connect(delete_article_media_files, sender=Article)
