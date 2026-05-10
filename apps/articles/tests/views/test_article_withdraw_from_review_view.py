# pylint: disable=R0801

from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from articles.models import Article, ArticleStatus
from users.models import User


class TestArticleWithdrawFromReviewView(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com"
        )

        self.article = Article.objects.create(
            title="Pending",
            slug="pending",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
        )

    def test_login_required(self):
        response = self.client.post(
            reverse("article-withdraw-from-review", kwargs={"pk": self.article.id})
        )

        login_url = reverse("login")
        expected_next = reverse(
            "article-withdraw-from-review",
            kwargs={"pk": self.article.id},
        )

        self.assertRedirects(response, f"{login_url}?next={expected_next}")

    def test_author_can_withdraw_article_from_review(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("article-withdraw-from-review", kwargs={"pk": self.article.id})
        )

        self.article.refresh_from_db()

        self.assertRedirects(
            response,
            reverse("article-update", kwargs={"pk": self.article.id}),
        )
        self.assertEqual(self.article.status, ArticleStatus.DRAFT)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Article was withdrawn from review.")

    def test_non_owner_gets_404(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("article-withdraw-from-review", kwargs={"pk": self.article.id})
        )

        self.assertEqual(response.status_code, 404)

    def test_missing_article_returns_404(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("article-withdraw-from-review", kwargs={"pk": 99999})
        )

        self.assertEqual(response.status_code, 404)

    @patch("articles.views.articles.withdraw_article_from_review")
    def test_shows_error_message_on_service_error(self, mocked_withdraw):
        mocked_withdraw.side_effect = ValueError("Error")

        self.client.force_login(self.author)
        response = self.client.post(
            reverse("article-withdraw-from-review", kwargs={"pk": self.article.id}),
            follow=True,
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, ArticleStatus.PENDING_REVIEW)

        mocked_withdraw.assert_called_once_with(article_id=self.article.id)

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages)
        self.assertEqual(str(messages[0]), "Error")
