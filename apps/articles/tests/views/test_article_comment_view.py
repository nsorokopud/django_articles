from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article, ArticleComment
from users.models import User


class TestArticleCommentView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="text1",
            content="content1",
        )
        self.url = reverse("article-comment", args=[self.article.slug])

    def test_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={self.url}",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(ArticleComment.objects.count(), 0)

    def test_non_existent_article(self):
        url = reverse("article-comment", args=["non-existent-article"])
        comment_data = {"text": "text"}

        self.client.force_login(self.user)
        response = self.client.post(url, comment_data)
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "error.html")
        self.assertEqual(ArticleComment.objects.count(), 0)

    def test_form_error(self):
        comment_data = {"text": ""}

        self.client.force_login(self.user)
        with (
            patch("articles.cache.get_redis_connection"),
            patch("articles.views.decorators.get_redis_connection"),
        ):
            response = self.client.post(self.url, comment_data)
            self.assertRedirects(
                response,
                reverse("article-details", args=[self.article.slug]),
                status_code=302,
                target_status_code=200,
            )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, 40)  # ERROR level
        self.assertEqual(messages[0].message, "Your comment could not be posted.")
        self.assertEqual(ArticleComment.objects.count(), 0)

    def test_correct_case(self):
        comment_data = {"text": "text"}

        self.client.force_login(self.user)
        with (
            patch("articles.cache.get_redis_connection"),
            patch("articles.views.decorators.get_redis_connection"),
        ):
            response = self.client.post(self.url, comment_data)
            self.assertRedirects(
                response,
                reverse("article-details", args=[self.article.slug]),
                status_code=302,
                target_status_code=200,
            )

        self.assertEqual(ArticleComment.objects.count(), 1)
        last_comment = ArticleComment.objects.last()
        self.assertEqual(last_comment.text, comment_data["text"])
        self.assertEqual(last_comment.article, self.article)
        self.assertEqual(last_comment.author, self.user)
