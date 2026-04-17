# pylint: disable=R0801

from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from articles.models import Article, ArticleStatus
from users.models import User


class TestArticleSubmitForReviewView(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com"
        )

        self.article = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            preview_text="p",
            content="c",
            status=ArticleStatus.DRAFT,
        )

    def test_login_required(self):
        response = self.client.post(
            reverse(
                "article-submit-for-review",
                kwargs={"article_slug": self.article.slug},
            )
        )

        login_url = reverse("login")
        expected_next = reverse(
            "article-submit-for-review",
            kwargs={"article_slug": self.article.slug},
        )

        self.assertRedirects(response, f"{login_url}?next={expected_next}")

    def test_author_can_submit_article_for_review(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse(
                "article-submit-for-review",
                kwargs={"article_slug": self.article.slug},
            )
        )

        self.article.refresh_from_db()

        self.assertRedirects(
            response,
            reverse("article-update", kwargs={"article_slug": self.article.slug}),
        )
        self.assertEqual(self.article.status, ArticleStatus.PENDING_REVIEW)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Article was submitted for review.")

    def test_non_owner_gets_404(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse(
                "article-submit-for-review",
                kwargs={"article_slug": self.article.slug},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_missing_article_returns_404(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse(
                "article-submit-for-review",
                kwargs={"article_slug": "missing-slug"},
            )
        )

        self.assertEqual(response.status_code, 404)

    @patch("articles.views.articles.submit_article_for_review")
    def test_shows_error_message_on_service_error(self, mocked_submit):
        mocked_submit.side_effect = ValueError("Error")

        self.client.force_login(self.author)
        response = self.client.post(
            reverse(
                "article-submit-for-review",
                kwargs={"article_slug": self.article.slug},
            ),
            follow=True,
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, ArticleStatus.DRAFT)

        mocked_submit.assert_called_once_with(article_id=self.article.id)

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages)
        self.assertEqual(str(messages[0]), "Error")
