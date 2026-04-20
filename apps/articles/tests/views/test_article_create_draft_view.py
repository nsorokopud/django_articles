from django.test import TestCase
from django.urls import reverse

from articles.models import Article, ArticleStatus
from users.models import User


class TestArticleCreateDraftView(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="author", email="author@test.com")
        self.url = reverse("article-create-draft")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.post(self.url)

        login_url = reverse("login")
        self.assertRedirects(response, f"{login_url}?next={self.url}")
        self.assertEqual(Article.objects.count(), 0)

    def test_post_creates_empty_draft_for_authenticated_user(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(Article.objects.count(), 1)

        article = Article.objects.get()
        self.assertEqual(article.author, self.user)
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertEqual(article.title, "Untitled article")
        self.assertEqual(article.preview_text, "")
        self.assertEqual(article.content, "")
        self.assertTrue(article.slug)

        self.assertRedirects(
            response,
            reverse("article-update", kwargs={"article_slug": article.slug}),
        )

    def test_each_post_creates_new_draft(self):
        self.client.force_login(self.user)

        response1 = self.client.post(self.url)
        response2 = self.client.post(self.url)

        self.assertEqual(Article.objects.count(), 2)

        articles = Article.objects.order_by("id")
        self.assertNotEqual(articles[0].slug, articles[1].slug)
        self.assertEqual(articles[0].status, ArticleStatus.DRAFT)
        self.assertEqual(articles[1].status, ArticleStatus.DRAFT)

        self.assertRedirects(
            response1,
            reverse("article-update", kwargs={"article_slug": articles[0].slug}),
        )
        self.assertRedirects(
            response2,
            reverse("article-update", kwargs={"article_slug": articles[1].slug}),
        )

    def test_get_is_not_allowed(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(Article.objects.count(), 0)
