from django.apps import AppConfig
from django.db.models.signals import post_save


class ArticlesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'articles'

    def ready(self):
        from .models import Article
        from .signals import send_article_notification

        post_save.connect(send_article_notification, sender=Article)
