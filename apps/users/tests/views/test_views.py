from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def test_post_registration_view(self):
        response = self.client.get(reverse("post-registration"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/post_registration.html")

        response = self.client.post(reverse("post-registration"))
        self.assertEqual(response.status_code, 405)

    def test_author_subscribe_view(self):
        author = User.objects.create_user(username="author1")

        target_url = reverse("author-subscribe", kwargs={"author_id": author.id})
        response = self.client.post(target_url)

        redirect_url = f"{reverse('login')}?next={target_url}"
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

        self.client.force_login(self.test_user)
        self.assertTrue(self.test_user not in author.subscribers.all())

        response = self.client.post(target_url)
        redirect_url = reverse("author-page", kwargs={"author_id": author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertTrue(self.test_user in author.subscribers.all())

        response = self.client.post(target_url)
        redirect_url = reverse("author-page", kwargs={"author_id": author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertTrue(self.test_user not in author.subscribers.all())
