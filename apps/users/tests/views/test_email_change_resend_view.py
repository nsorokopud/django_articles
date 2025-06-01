from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestEmailChangeResendView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("email-change-resend")
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_post_anonymous_user(self):
        redirect_url = f'{reverse("login")}?next={self.url}'
        response = self.client.post(self.url)
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    @patch("users.views.get_pending_email_address")
    @patch("users.views.send_email_change_link")
    def test_post_no_pending_email(self, mock_send_email, mock_get_pending_email):
        mock_get_pending_email.return_value = None

        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse("email-change"), status_code=302, target_status_code=200
        )
        mock_send_email.assert_not_called()

    @patch("users.views.email.get_pending_email_address")
    @patch("users.views.email.send_email_change_link")
    def test_post_with_pending_email(self, mock_send_email, mock_get_pending_email):
        email = EmailAddress(
            user=self.user, email=self.user.email, primary=False, verified=False
        )
        mock_get_pending_email.return_value = email

        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse("email-change"), status_code=302, target_status_code=200
        )
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        self.assertEqual(len(args), 3)
        self.assertEqual(args[0], self.user)
        self.assertEqual(args[1], email.email)
        self.assertEqual(args[2], response.wsgi_request.build_absolute_uri("/"))
        self.assertEqual(kwargs, {})
