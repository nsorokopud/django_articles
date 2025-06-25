from unittest.mock import patch

from django.test import TestCase, override_settings

from articles.models import Article, ArticleCategory, User
from config.settings import CACHES


class TestArticleModel(TestCase):
    @override_settings(CACHES=CACHES)
    def test_views_property(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        cat = ArticleCategory.objects.create(title="cat", slug="cat")

        a = Article.objects.create(
            title="a",
            category=cat,
            author=user,
            preview_text="text1",
            content="c",
        )
        self.assertEqual(a.views, 0)

        a.views_count = 10
        a.save(update_fields=["views_count"])

        with patch("articles.cache.get_cached_article_views") as mock_get_cached:
            mock_get_cached.return_value = 5
            self.assertEqual(a.views, 15)
            mock_get_cached.assert_called_once_with(a.id)
