from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article, ArticleCategory, ArticleComment
from users.models import User


class TestArticleDetailView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.user,
            preview_text="1",
            content="1",
            is_published=True,
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.user, text="comment"
        )

    def test_get(self):
        response = self.client.get(reverse("article-details", args=[self.article.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article.html")

        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)

    def test_views_counter_increments_once_per_session(self):
        url = reverse("article-details", args=[self.article.slug])
        user2 = User.objects.create_user(username="user2", email="user2@test.com")
        self.assertEqual(self.article.views_count, 0)

        self.client.get(url)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)

        self.client.force_login(self.user)
        self.client.get(url)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)

        self.client.force_login(user2)
        self.client.get(url)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 2)

        self.client.get(url)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 2)
