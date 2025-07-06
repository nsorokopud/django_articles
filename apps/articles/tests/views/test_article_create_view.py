from unittest.mock import ANY

from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article
from users.models import User


class TestArticleCreateView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("article-create")
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_get_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

    def test_get_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")

    def test_post_anonymous_user(self):
        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

    def test_post_invalid_data(self):
        with self.assertRaises(Article.DoesNotExist):
            Article.objects.get(slug="a1")

        self.client.force_login(self.user)
        response = self.client.post(
            self.url, {"title": "a1"}, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["status"], "fail")
        self.assertEqual(
            response_json["data"],
            {
                "preview_text": ["This field is required."],
                "content": ["This field is required."],
            },
        )
        self.assertEqual(Article.objects.count(), 0)

    def test_post_correct(self):
        article_data = {"title": "a1", "preview_text": "1", "content": "1"}

        self.client.force_login(self.user)
        response = self.client.post(
            self.url, article_data, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["status"], "success")
        self.assertEqual(
            response_json["data"],
            {
                "articleId": ANY,
                "articleSlug": article_data["title"],
                "articleUrl": "/articles/a1",
            },
        )
        self.assertIsInstance(response_json["data"]["articleId"], int)

        self.assertEqual(Article.objects.count(), 1)

        a = Article.objects.get(slug="a1")
        self.assertEqual(a.title, article_data["title"])
        self.assertEqual(a.slug, article_data["title"])
        self.assertEqual(a.author, self.user)
        self.assertEqual(a.category, None)
        self.assertCountEqual(a.tags.all(), [])
        self.assertEqual(a.preview_text, article_data["preview_text"])
        self.assertEqual(a.content, article_data["content"])
        with self.assertRaises(ValueError):
            a.preview_image.url
        self.assertEqual(a.is_published, True)
