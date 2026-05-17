from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from users.models import User


class TestEmailChangeConfirmationView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="u@test.com")
        self.token = "test-token"
        self.url = reverse("email-change-confirm", kwargs={"token": self.token})

    def test_get_redirects_anonymous_user_to_login(self):
        response = self.client.get(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_get_authenticated_user_renders_confirmation_form(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].user, self.user)
        self.assertEqual(response.context["form"].initial["token"], self.token)

    def test_post_anonymous_user_redirects_to_login(self):
        response = self.client.post(self.url, {"token": self.token})
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    @patch("users.views.email.change_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    @patch("users.forms.get_pending_email_address")
    def test_post_valid_token_changes_email(
        self, mock_get_pending_email, mock_check_token, mock_change_email
    ):
        pending_email = Mock()
        pending_email.email = "pending@test.com"

        mock_get_pending_email.return_value = pending_email
        mock_check_token.return_value = True

        self.client.force_login(self.user)
        response = self.client.post(self.url, {"token": self.token})

        self.assertRedirects(response, reverse("email-change"))
        mock_get_pending_email.assert_called_once_with(self.user)
        mock_check_token.assert_called_once_with(self.user, self.token)
        mock_change_email.assert_called_once_with(self.user.id)

    @patch("users.views.email.change_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    @patch("users.forms.get_pending_email_address")
    def test_post_invalid_token_shows_form_error(
        self, mock_get_pending_email, mock_check_token, mock_change_email
    ):
        pending_email = Mock()
        pending_email.email = "pending@test.com"

        mock_get_pending_email.return_value = pending_email
        mock_check_token.return_value = False

        self.client.force_login(self.user)
        response = self.client.post(self.url, {"token": self.token})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].initial["token"], self.token)
        self.assertFormError(response.context["form"], None, "Invalid token.")
        mock_get_pending_email.assert_called_once_with(self.user)
        mock_check_token.assert_called_once_with(self.user, self.token)
        mock_change_email.assert_not_called()

    @patch("users.views.email.change_email_address")
    @patch("users.forms.get_pending_email_address")
    def test_post_without_pending_email_shows_form_error(
        self, mock_get_pending_email, mock_change_email
    ):
        mock_get_pending_email.return_value = None

        self.client.force_login(self.user)
        response = self.client.post(self.url, {"token": self.token})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].initial["token"], self.token)
        self.assertFormError(
            response.context["form"],
            None,
            "You don't have any pending email addresses.",
        )
        mock_get_pending_email.assert_called_once_with(self.user)
        mock_change_email.assert_not_called()
