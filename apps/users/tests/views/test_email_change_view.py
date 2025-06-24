from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestEmailChangeView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("email-change")
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_get_anonymous_user(self):
        response = self.client.get(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_get_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change.html")
        self.assertEqual(response.context["form"].user, self.user)
        self.assertEqual(response.context["pending_email"], None)

        email = EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=False, verified=False
        )
        response = self.client.get(self.url)
        self.assertEqual(response.context["pending_email"], email)

    def test_post_anonymous_user(self):
        response = self.client.post(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    @patch("users.views.send_email_change_link")
    def test_post_invalid_data(self, mock_send_email):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        mock_send_email.assert_not_called()

    @patch("users.views.email.send_email_change_link")
    def test_post_valid_data(self, mock_send_email):
        data = {"new_email": "new@test.com"}

        self.client.force_login(self.user)
        response = self.client.post(self.url, data)
        self.assertRedirects(response, self.url)

        email = EmailAddress.objects.get(
            user=self.user, primary=False, verified=False
        ).email
        self.assertEqual(email, "new@test.com")
        mock_send_email.assert_called_once_with(
            self.user, email, response.wsgi_request.build_absolute_uri("/")
        )
