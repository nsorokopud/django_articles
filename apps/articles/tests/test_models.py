from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from articles.models import Article, ArticleStatus
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

        self.published_article = Article.objects.create(
            title="published article",
            author=self.user,
            preview_text="published preview",
            content="published content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )

    @patch("articles.services.generate_unique_article_slug", return_value="slug1")
    def test_slug_generated_when_article_first_saved(self, mock_generate_slug):
        article = Article(
            title="a1",
            author=self.user,
            preview_text="a1",
            content="a1",
        )

        mock_generate_slug.assert_not_called()

        article.save()

        mock_generate_slug.assert_called_once_with("a1")
        article.refresh_from_db()
        self.assertEqual(article.slug, "slug1")

    @patch("articles.services.generate_unique_article_slug")
    def test_slug_not_generated_on_create_when_slug_already_set(
        self, mock_generate_slug
    ):
        article = Article(
            title="a1",
            slug="custom-slug",
            author=self.user,
            preview_text="a1",
            content="a1",
        )

        article.save()

        mock_generate_slug.assert_not_called()
        article.refresh_from_db()
        self.assertEqual(article.slug, "custom-slug")

    @patch(
        "articles.services.generate_unique_article_slug",
        return_value="updated-draft-slug",
    )
    def test_slug_regenerated_when_title_changed_for_unpublished_article(
        self, mock_generate_slug
    ):
        old_slug = self.unpublished_article.slug

        self.unpublished_article.title = "updated draft title"
        self.unpublished_article.save()

        mock_generate_slug.assert_called_once_with("updated draft title")
        self.unpublished_article.refresh_from_db()
        self.assertEqual(self.unpublished_article.title, "updated draft title")
        self.assertEqual(self.unpublished_article.slug, "updated-draft-slug")
        self.assertNotEqual(self.unpublished_article.slug, old_slug)

    @patch("articles.services.generate_unique_article_slug")
    def test_slug_not_regenerated_when_title_not_changed_for_unpublished_article(
        self, mock_generate_slug
    ):
        original_slug = self.unpublished_article.slug

        self.unpublished_article.preview_text = "updated preview only"
        self.unpublished_article.save()

        mock_generate_slug.assert_not_called()
        self.unpublished_article.refresh_from_db()
        self.assertEqual(self.unpublished_article.slug, original_slug)

    @patch("articles.services.generate_unique_article_slug")
    def test_slug_not_regenerated_when_title_changed_for_published_article(
        self, mock_generate_slug
    ):
        original_slug = self.published_article.slug

        self.published_article.title = "updated published title"
        self.published_article.save()

        mock_generate_slug.assert_not_called()
        self.published_article.refresh_from_db()
        self.assertEqual(self.published_article.title, "updated published title")
        self.assertEqual(self.published_article.slug, original_slug)

    @patch("articles.services.generate_unique_article_slug")
    def test_slug_not_regenerated_when_title_not_changed_for_published_article(
        self, mock_generate_slug
    ):
        original_slug = self.published_article.slug

        self.published_article.preview_text = "updated published preview only"
        self.published_article.save()

        mock_generate_slug.assert_not_called()
        self.published_article.refresh_from_db()
        self.assertEqual(self.published_article.slug, original_slug)

    @override_settings(CACHES=CACHES)
    def test_views_property(self):
        self.assertEqual(self.unpublished_article.views, 0)

        self.unpublished_article.views_count = 10
        self.unpublished_article.save(update_fields=["views_count"])

        with patch("articles.cache.get_cached_article_views") as mock_get_cached:
            mock_get_cached.return_value = 5
            self.assertEqual(self.unpublished_article.views, 15)
            mock_get_cached.assert_called_once_with(self.unpublished_article.id)
