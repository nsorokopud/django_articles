from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from articles.models import Article
from config.settings import CACHES


User = get_user_model()


class TestArticleModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.a = Article.objects.create(
            title="a",
            author=self.user,
            preview_text="a",
            content="a",
        )

    @patch("articles.services.generate_unique_article_slug", return_value="slug1")
    def test_slug_generated_when_article_first_saved(self, mock_generate_slug):
        a = Article(
            title="a1",
            author=self.user,
            preview_text="a1",
            content="a1",
        )
        mock_generate_slug.assert_not_called()

        a.save()
        mock_generate_slug.assert_called_once_with(a.title)
        a.refresh_from_db()
        self.assertEqual(a.slug, "slug1")

    @patch("articles.services.generate_unique_article_slug", return_value="slug2")
    def test_slug_generated_when_title_changed_by_user(self, mock_generate_slug):
        self.a.title = "a2"
        self.a.save()
        mock_generate_slug.assert_called_once_with("a2")
        self.a.refresh_from_db()
        self.assertEqual(self.a.title, "a2")
        self.assertEqual(self.a.slug, "slug2")

    @patch("articles.services.generate_unique_article_slug", return_value="slug1")
    def test_slug_not_generated_when_title_not_changed(self, mock_generate_slug):
        self.a.title = "a"
        self.a.save()
        mock_generate_slug.assert_not_called()
        self.a.refresh_from_db()
        self.assertEqual(self.a.title, "a")
        self.assertEqual(self.a.slug, "a")

    @patch("articles.services.generate_unique_article_slug", return_value="slug1")
    def test_slug_not_generated_when_set_by_admin(self, mock_generate_slug):
        self.a.title = "a"
        self.a.slug = "abc"
        self.a.from_admin = True
        self.a.save()
        mock_generate_slug.assert_not_called()
        self.a.refresh_from_db()
        self.assertEqual(self.a.title, "a")
        self.assertEqual(self.a.slug, "abc")

    @override_settings(CACHES=CACHES)
    def test_views_property(self):
        self.assertEqual(self.a.views, 0)
        self.a.views_count = 10
        self.a.save(update_fields=["views_count"])

        with patch("articles.cache.get_cached_article_views") as mock_get_cached:
            mock_get_cached.return_value = 5
            self.assertEqual(self.a.views, 15)
            mock_get_cached.assert_called_once_with(self.a.id)
