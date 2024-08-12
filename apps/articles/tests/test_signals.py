from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TransactionTestCase

from ..models import Article, ArticleComment
from ..signals import send_article_notification, send_comment_notification


class TestSignals(TransactionTestCase):
    @classmethod
    def tearDownClass(cls):
        signals.post_save.connect(send_article_notification, sender=Article)
        signals.post_save.connect(send_comment_notification, sender=ArticleComment)

    def test_send_article_notification(self):
        user = User.objects.create_user(username="user")
        with patch(
            "notifications.tasks.send_new_article_notification.delay"
        ) as send_new_article_notification__mock:
            a = Article.objects.create(
                title="a1", slug="a1", author=user, preview_text="text", content="content"
            )
            send_new_article_notification__mock.assert_called_once_with(a.slug)

        signals.post_save.disconnect(send_article_notification, sender=Article)

        with patch(
            "notifications.tasks.send_new_article_notification.delay"
        ) as send_new_article_notification__mock:
            Article.objects.create(
                title="a2", slug="a2", author=user, preview_text="text", content="content"
            )
            send_new_article_notification__mock.assert_not_called()

    def test_send_comment_notification(self):
        user = User.objects.create_user(username="user")
        a = Article.objects.create(
            title="a1", slug="a1", author=user, preview_text="text", content="content"
        )

        with patch(
            "notifications.tasks.send_new_comment_notification.delay"
        ) as send_new_comment_notification__mock:
            c = ArticleComment.objects.create(article=a, author=user, text="1")
            send_new_comment_notification__mock.assert_called_once_with(c.id, user.id)

        signals.post_save.disconnect(send_comment_notification, sender=ArticleComment)

        with patch(
            "notifications.tasks.send_new_comment_notification.delay"
        ) as send_new_comment_notification__mock:
            ArticleComment.objects.create(article=a, author=user, text="2")
            send_new_comment_notification__mock.assert_not_called()
