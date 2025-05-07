from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestPasswordResetView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("password-reset")
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="Abcd1234!"
        )

    def test_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_reset.html")

    def test_post(self):
        incorrect_data = {"email": "non-existent@test.com"}
        response = self.client.post(self.url, incorrect_data)
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(len(mail.outbox), 0)

        data = {"email": self.user.email}
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.user.email], mail.outbox[0].to)
        self.assertEqual("Password reset on testserver", mail.outbox[0].subject)
