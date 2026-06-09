from django.test import Client, TestCase, override_settings
from django.urls import reverse

from users.models import User


class TestPasswordResetView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("password-reset")
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="Abcd1234!", is_active=True
        )

    def test_get(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_reset.html")

    @override_settings(RATELIMIT_ENABLE=True)
    def test_is_rate_limited(self):
        for _ in range(3):
            self.client.post(self.url, {"email": self.user.email})

        response = self.client.post(self.url, {"email": self.user.email})

        self.assertEqual(response.status_code, 429)
