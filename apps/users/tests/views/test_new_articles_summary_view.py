from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from users.models import User


class TestNewArticlesSummaryView(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="u",
            email="u@test.com",
        )
        self.url = reverse("new-articles-summary")

    def test_requires_login(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    @patch("users.views.subscriptions.get_new_articles_summary")
    def test_calls_service_with_default_since_publish_sequence_zero(
        self,
        mock_get_new_articles_summary,
    ) -> None:
        self.client.force_login(self.user)
        mock_get_new_articles_summary.return_value = {
            "has_new": False,
            "latest_article_publish_sequence": 0,
        }

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "has_new": False,
                "latest_article_publish_sequence": 0,
            },
        )
        mock_get_new_articles_summary.assert_called_once_with(
            user_id=self.user.id,
            since_publish_sequence=0,
        )

    @patch("users.views.subscriptions.get_new_articles_summary")
    def test_calls_service_with_parsed_since_publish_sequence(
        self,
        mock_get_new_articles_summary,
    ) -> None:
        self.client.force_login(self.user)
        mock_get_new_articles_summary.return_value = {
            "has_new": True,
            "latest_article_publish_sequence": 123,
        }

        response = self.client.get(self.url, {"since_publish_sequence": "123"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "has_new": True,
                "latest_article_publish_sequence": 123,
            },
        )
        mock_get_new_articles_summary.assert_called_once_with(
            user_id=self.user.id,
            since_publish_sequence=123,
        )

    @patch("users.views.subscriptions.get_new_articles_summary")
    def test_invalid_since_publish_sequence_returns_bad_request(
        self,
        mock_get_new_articles_summary,
    ) -> None:
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"since_publish_sequence": "abc"})

        self.assertEqual(response.status_code, 400)
        mock_get_new_articles_summary.assert_not_called()
