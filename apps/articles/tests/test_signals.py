from unittest.mock import patch

from django.db.models import signals
from django.test import TransactionTestCase

from users.models import User

from ..models import Article
from ..signals import delete_article_media_files


class TestSignals(TransactionTestCase):
    @classmethod
    def tearDownClass(cls):
        signals.post_delete.connect(delete_article_media_files, sender=Article)

    def test_delete_article_media_files(self):
        user = User.objects.create(username="user")
        a1 = Article.objects.create(
            title="a1", slug="a1", author=user, preview_text="a1", content="a1"
        )

        with patch("articles.signals.delete_article_inline_media_task.delay") as mock:
            a1_id = a1.id
            a1.delete()
            mock.assert_called_once_with(a1_id, user.id)

        a2 = Article.objects.create(
            title="a2", slug="a2", author=user, preview_text="a2", content="a2"
        )

        signals.post_delete.disconnect(delete_article_media_files, sender=Article)

        with patch("articles.signals.delete_article_inline_media_task.delay") as mock:
            a2.delete()
            mock.assert_not_called()
