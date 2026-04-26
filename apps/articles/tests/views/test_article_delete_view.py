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
            username="test_user",
            email="test@test.com",
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            email="other@test.com",
        )
        self.test_category = ArticleCategory.objects.create(
            title="cat1",
            slug="cat1",
        )
        self.test_article = Article.objects.create(
            title="test_article",
            slug="test-article",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            content_text="content1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )

    def _article(self, **overrides):
        data = {
            "title": "title",
            "slug": "slug",
            "category": self.test_category,
            "author": self.test_user,
            "preview_text": "text",
            "content": "content",
            "content_text": "content",
            "status": ArticleStatus.DRAFT,
        }
        data.update(overrides)
        return Article.objects.create(**data)

    def test_anonymous_redirects_to_login(self):
        url = reverse("article-delete", args=[self.test_article.slug])
        redirect_url = f"{reverse('login')}?next={url}"

        response = self.client.get(url)
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    @patch("articles.views.articles.delete_article")
    def test_authorized_calls_delete_service_and_redirects(self, mock_delete_article):
        article = self._article(slug="draft-slug")

        self.client.force_login(self.test_user)
        response = self.client.post(reverse("article-delete", args=[article.slug]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("my-articles"))
        mock_delete_article.assert_called_once_with(article_id=article.id)

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("deleted successfully" in str(m) for m in messages))

    def test_authorized_deletes_draft_article_end_to_end(self):
        article = self._article(slug="draft-delete")

        self.client.force_login(self.test_user)
        response = self.client.post(reverse("article-delete", args=[article.slug]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("my-articles"))
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())

    def test_forbids_published_article(self):
        self.client.force_login(self.test_user)

        response = self.client.post(
            reverse("article-delete", args=[self.test_article.slug])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Article.objects.filter(pk=self.test_article.pk).exists())

    def test_forbids_pending_review_article(self):
        article = self._article(
            slug="pending-slug",
            status=ArticleStatus.PENDING_REVIEW,
        )

        self.client.force_login(self.test_user)
        response = self.client.post(reverse("article-delete", args=[article.slug]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Article.objects.filter(pk=article.pk).exists())

    def test_forbids_access_not_by_author(self):
        article = self._article(slug="someone-elses-article")

        self.client.force_login(self.other_user)
        response = self.client.post(reverse("article-delete", args=[article.slug]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Article.objects.filter(pk=article.pk).exists())
