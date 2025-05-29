from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestAuthorSubscribeView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.author = User.objects.create_user(username="author")
        self.target_url = reverse(
            "author-subscribe", kwargs={"author_id": self.author.id}
        )

    def test_post_anonymous_user(self):
        response = self.client.post(self.target_url)
        redirect_url = f"{reverse('login')}?next={self.target_url}"
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_post_user_not_subscribed(self):
        self.assertFalse(self.user in self.author.subscribers.all())

        self.client.force_login(self.user)
        response = self.client.post(self.target_url)
        redirect_url = reverse("author-page", kwargs={"author_id": self.author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertTrue(self.user in self.author.subscribers.all())

    def test_post_user_subscribed(self):
        self.author.subscribers.add(self.user)
        self.assertTrue(self.user in self.author.subscribers.all())

        self.client.force_login(self.user)
        response = self.client.post(self.target_url)
        redirect_url = reverse("author-page", kwargs={"author_id": self.author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertFalse(self.user in self.author.subscribers.all())
