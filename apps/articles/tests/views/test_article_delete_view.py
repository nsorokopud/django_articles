from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from users.models import User


class TestArticleDeleteView(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )
        self.test_category = ArticleCategory.objects.create(title="cat1", slug="cat1")
        self.test_article = Article.objects.create(
            title="test_article",
            slug="test-article",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )

    def test_unauthorized(self):
        url = reverse("article-delete", args=[self.test_article.slug])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    @patch("articles.views.articles.invalidate_article_slug_id")
    def test_authorized(self, mock_invalidate):
        a = Article.objects.create(
            title="title",
            slug="slug",
            category=self.test_category,
            preview_text="text",
            content="content",
            author=self.test_user,
            status=ArticleStatus.DRAFT,
        )

        self.client.force_login(self.test_user)
        response = self.client.post(reverse("article-delete", args=[a.slug]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("my-articles"))

        mock_invalidate.assert_called_once_with(article_slug="slug")

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("deleted successfully" in str(m) for m in messages))

        with self.assertRaises(Article.DoesNotExist):
            Article.objects.get(pk=a.pk)

    @patch("articles.views.articles.invalidate_article_slug_id")
    def test_forbids_published_article(self, mock_invalidate):
        self.client.force_login(self.test_user)
        response = self.client.post(
            reverse("article-delete", args=[self.test_article.slug])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Article.objects.filter(pk=self.test_article.pk).exists())
        mock_invalidate.assert_not_called()

    @patch("articles.views.articles.invalidate_article_slug_id")
    def test_forbids_pending_review_article(self, mock_invalidate):
        article = Article.objects.create(
            title="title",
            slug="pending-slug",
            category=self.test_category,
            preview_text="text",
            content="content",
            author=self.test_user,
            status=ArticleStatus.PENDING_REVIEW,
        )

        self.client.force_login(self.test_user)
        response = self.client.post(reverse("article-delete", args=[article.slug]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Article.objects.filter(pk=article.pk).exists())
        mock_invalidate.assert_not_called()
