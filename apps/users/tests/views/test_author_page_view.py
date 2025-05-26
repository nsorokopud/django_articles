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

    def test_author_page_loads(self):
        response = self.client.get(
            reverse("author-page", kwargs={"author_id": self.author.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/author_page.html")

    def test_subscriber_count_cached(self):
        cache.clear()
        self.client.get(reverse("author-page", kwargs={"author_id": self.author.id}))
        cache_key = get_subscribers_count_cache_key(self.author.id)
        self.assertEqual(cache.get(cache_key), 0)
