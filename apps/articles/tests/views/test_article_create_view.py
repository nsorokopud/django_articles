from datetime import datetime, timezone
from unittest.mock import ANY, patch

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

    def test_post_correct_creates_draft_for_regular_user(self):
        article_data = {"title": "a1", "preview_text": "1", "content": "1"}

        self.client.force_login(self.user)
        response = self.client.post(
            self.url, article_data, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)

        response_json = response.json()
        self.assertEqual(response_json["status"], "success")

        expected_url = reverse(
            "article-update",
            kwargs={"article_slug": article_data["title"]},
        )

        self.assertEqual(
            response_json["data"],
            {
                "articleId": ANY,
                "articleSlug": article_data["title"],
                "articleUrl": expected_url,
                "isPublished": False,
            },
        )
        self.assertIsInstance(response_json["data"]["articleId"], int)

        self.assertEqual(Article.objects.count(), 1)

        a = Article.objects.get(slug="a1")
        self.assertEqual(a.title, article_data["title"])
        self.assertEqual(a.slug, article_data["title"])
        self.assertEqual(a.author, self.user)
        self.assertIsNone(a.category)
        self.assertCountEqual(a.tags.all(), [])
        self.assertEqual(a.preview_text, article_data["preview_text"])
        self.assertEqual(a.content, article_data["content"])
        with self.assertRaises(ValueError):
            a.preview_image.url
        self.assertIsNone(a.published_at)
        self.assertIsNone(a.publish_sequence)

    @patch(
        "articles.services.publishing.get_next_article_publish_sequence_value",
        return_value=999,
    )
    @patch(
        "articles.services.publishing.timezone.now",
        return_value=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    def test_post_correct_publishes_for_staff_user(self, mock_now, mock_get_next):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

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
                "articleUrl": reverse(
                    "article-details",
                    kwargs={"article_slug": article_data["title"]},
                ),
                "isPublished": True,
            },
        )

        a = Article.objects.get(slug="a1")
        self.assertEqual(a.title, article_data["title"])
        self.assertEqual(a.slug, article_data["title"])
        self.assertEqual(a.author, self.user)
        self.assertEqual(a.preview_text, article_data["preview_text"])
        self.assertEqual(a.content, article_data["content"])
        self.assertEqual(a.published_at, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(a.publish_sequence, 999)
