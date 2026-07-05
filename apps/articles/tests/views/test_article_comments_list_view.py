# pylint: disable=R0801


from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from users.models import User


@override_settings(ARTICLES_COMMENTS_PER_PAGE=2)
class TestArticleCommentsListView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com"
        )
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.user,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
        )

        self.comment1 = ArticleComment.objects.create(
            article=self.article, author=self.user, text="comment 1"
        )
        self.comment2 = ArticleComment.objects.create(
            article=self.article, author=self.user, text="comment 2"
        )
        self.comment3 = ArticleComment.objects.create(
            article=self.article, author=self.user, text="comment 3"
        )

        self.url = reverse("article-comments-list", args=[self.article.slug])

    def test_returns_first_comments_page(self):
        response = self.client.get(self.url, {"page": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["hasNext"])
        self.assertEqual(payload["nextPage"], 2)

        self.assertIn("comment 3", payload["html"])
        self.assertIn("comment 2", payload["html"])
        self.assertNotIn("comment 1", payload["html"])

    def test_returns_next_comments_page(self):
        response = self.client.get(self.url, {"page": 2})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["hasNext"])
        self.assertIsNone(payload["nextPage"])

        self.assertIn("comment 1", payload["html"])
        self.assertNotIn("comment 2", payload["html"])
        self.assertNotIn("comment 3", payload["html"])

    def test_authenticated_user_sees_liked_comment_active(self):
        self.comment3.users_that_liked.add(self.user)
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"page": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("comment 3", payload["html"])
        self.assertIn("active", payload["html"])

    def test_anonymous_user_can_load_comments(self):
        response = self.client.get(self.url, {"page": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["status"], "success")
        self.assertIn("comment 3", payload["html"])

    def test_unpublished_article_returns_404(self):
        draft = Article.objects.create(
            title="draft",
            slug="draft",
            category=self.category,
            author=self.user,
            preview_text="preview",
            content="content",
            status=ArticleStatus.DRAFT,
        )

        response = self.client.get(
            reverse("article-comments-list", args=[draft.slug]), {"page": 1}
        )

        self.assertEqual(response.status_code, 404)

    def test_missing_article_returns_404(self):
        response = self.client.get(
            reverse("article-comments-list", args=["missing-slug"]), {"page": 1}
        )

        self.assertEqual(response.status_code, 404)
