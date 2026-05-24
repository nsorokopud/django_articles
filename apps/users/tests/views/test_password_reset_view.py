from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from users.models import User
from users.services.tokens import password_reset_token_generator


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

    def test_post_unknown_email_does_not_send_email_or_advance_token_version(self):
        response = self.client.post(self.url, {"email": "non-existent@test.com"})

        self.assertRedirects(response, reverse("login"))
        self.assertEqual(len(mail.outbox), 0)

        self.user.refresh_from_db()
        self.assertEqual(self.user.password_reset_token_version, 0)

    def test_post_existing_email_invalidates_previous_password_reset_token(self):
        old_token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(
            password_reset_token_generator.check_token(self.user, old_token)
        )

        response = self.client.post(self.url, {"email": self.user.email})

        self.assertRedirects(response, reverse("login"))

        self.user.refresh_from_db()

        self.assertFalse(
            password_reset_token_generator.check_token(self.user, old_token)
        )

    def test_post_existing_email_sends_email_and_advances_token_version(self):
        response = self.client.post(self.url, {"email": self.user.email})

        self.assertRedirects(response, reverse("login"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.password_reset_token_version, 1)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    @override_settings(RATELIMIT_ENABLE=True)
    def test_is_rate_limited(self):
        for _ in range(5):
            self.client.post(self.url, {"email": self.user.email})

        response = self.client.post(self.url, {"email": self.user.email})

        self.assertEqual(response.status_code, 429)
