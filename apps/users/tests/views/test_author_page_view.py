from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from users.cache import get_subscribers_count_cache_key
from users.models import User


class TestAuthorPageView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.url = reverse("author-page", kwargs={"author_id": self.author.id})

    def test_author_page_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/author_page.html")

    def test_context_subscribed_viewer(self):
        self.author.subscribers.add(self.user)
        self.client.force_login(self.user)

        response = self.client.get(self.url)
        self.assertEqual(response.context["author"], self.author)
        self.assertEqual(
            response.context["author_image_url"], self.author.profile.image.url
        )
        self.assertEqual(response.context["subscribers_count"], 1)
        self.assertTrue(response.context["is_viewer_subscribed"])

    def test_context_anonymous_viewer(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["author"], self.author)
        self.assertEqual(
            response.context["author_image_url"], self.author.profile.image.url
        )
        self.assertEqual(response.context["subscribers_count"], 0)
        self.assertFalse(response.context["is_viewer_subscribed"])

    def test_subscriber_count_cached(self):
        cache.clear()
        self.client.get(self.url)
        cache_key = get_subscribers_count_cache_key(self.author.id)
        self.assertEqual(cache.get(cache_key), 0)
