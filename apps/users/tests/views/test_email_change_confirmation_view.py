from unittest.mock import patch

from allauth.conftest import EmailAddress
from django.test import TestCase
from django.urls import reverse

from users.models import User


class EmailChangeConfirmationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.token = "test-token"
        self.url = reverse("email-change-confirm", kwargs={"token": self.token})

    def test_get(self):
        response = self.client.get(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].user, self.user)
        self.assertEqual(response.context["form"].initial["token"], self.token)

    def test_post_anonymous_user(self):
        redirect_url = f'{reverse("login")}?next={self.url}'
        response = self.client.post(self.url, {"token": self.token})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    @patch("users.forms.get_pending_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    @patch("users.views.change_email_address")
    def test_post_valid_token(
        self, mock_change_email, mock_check_token, mock_get_pending_email
    ):
        mock_check_token.return_value = True
        mock_get_pending_email.return_value = EmailAddress.objects.create(
            user=self.user, email="pending@test.com", primary=False, verified=False
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, {"token": self.token})
        self.assertRedirects(response, reverse("email-change"))
        mock_change_email.assert_called_once_with(self.user.id)

    @patch("users.forms.get_pending_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_post_invalid_token(self, mock_check_token, mock_get_pending_email):
        mock_check_token.return_value = False
        mock_get_pending_email.return_value = EmailAddress.objects.create(
            user=self.user, email="pending@test.com", primary=False, verified=False
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, {"token": self.token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["token"], self.token)
        self.assertEqual(
            response.context["form"].errors, {"__all__": ["Invalid token."]}
        )
