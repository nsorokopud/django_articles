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
