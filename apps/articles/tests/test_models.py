from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from articles.models import Article
from config.settings import CACHES


User = get_user_model()


class TestArticleModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")

        self.unpublished_article = Article.objects.create(
            title="draft article",
            author=self.user,
            preview_text="draft preview",
            content="draft content",
        )

    @override_settings(CACHES=CACHES)
    def test_views_property(self):
        self.assertEqual(self.unpublished_article.views, 0)

        self.unpublished_article.views_count = 10
        self.unpublished_article.save(update_fields=["views_count"])

        with patch("articles.cache.get_cached_article_views") as mock_get_cached:
            mock_get_cached.return_value = 5
            self.assertEqual(self.unpublished_article.views, 15)
            mock_get_cached.assert_called_once_with(self.unpublished_article.id)
