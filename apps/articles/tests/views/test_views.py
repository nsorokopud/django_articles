from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from users.models import User


class TestViews(TestCase):
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
        self.test_article.tags.add("tag1")
        self.test_article.save()
        self.test_comment = ArticleComment.objects.create(
            article=self.test_article, author=self.test_user, text="text"
        )

    def test_homepage_view(self):
        with patch("articles.cache.view_counts.get_redis_connection"):
            response = self.client.get(reverse("home"))

            self.assertRedirects(
                response,
                reverse("articles"),
                status_code=302,
                target_status_code=200,
            )

    def test_article_list_filter_view(self):
        with patch("articles.cache.view_counts.get_redis_connection"):
            response = self.client.get(reverse("articles"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_list_page.html")
        self.assertEqual(response.context["page_title"], "Articles matching your query")
        self.assertEqual(
            response.context["empty_message"], "No articles matching your query"
        )
        self.assertTrue(response.context["show_filters"])

    def test_article_delete_view_unauthorized(self):
        url = reverse("article-delete", args=[self.test_article.slug])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    @patch("articles.views.articles.invalidate_article_slug_id")
    def test_article_delete_view_authorized(self, mock_invalidate):
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
    def test_article_delete_view_forbids_published_article(self, mock_invalidate):
        article = Article.objects.create(
            title="title",
            slug="published-slug",
            category=self.test_category,
            preview_text="text",
            content="content",
            author=self.test_user,
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=2,
        )

        self.client.force_login(self.test_user)

        response = self.client.post(reverse("article-delete", args=[article.slug]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Article.objects.filter(pk=article.pk).exists())
        mock_invalidate.assert_not_called()

    @patch("articles.views.articles.invalidate_article_slug_id")
    def test_article_delete_view_forbids_pending_review_article(self, mock_invalidate):
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
