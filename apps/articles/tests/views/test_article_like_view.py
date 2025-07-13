from django.db.models import Count
from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article
from config.settings import LOGIN_URL
from users.models import User


class TestArticleLikeView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="article",
            slug="article",
            author=self.user,
            preview_text="text1",
            content="content1",
        )
        self.url = reverse("article-like", args=[self.article.slug])

    def test_anonymous_user_gets_redirected(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse(LOGIN_URL)}?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            f"{reverse(LOGIN_URL)}?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_post(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "data": {"likes": 1}})
        self.assertCountEqual(list(self.article.users_that_liked.all()), [self.user])
        likes_count = (
            Article.objects.filter(slug=self.article.slug)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 1)

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "data": {"likes": 0}})
        self.assertCountEqual(list(self.article.users_that_liked.all()), [])
        likes_count = (
            Article.objects.filter(slug=self.article.slug)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 0)
