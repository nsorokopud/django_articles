from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from users.models import PendingEmailChange, User


class TestEmailChangeConfirmationView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="u@test.com")
        self.pending_email_change = PendingEmailChange.objects.create(
            user=self.user, email="pending@test.com"
        )
        self.token = "test-token"
        self.url = reverse(
            "email-change-confirm",
            kwargs={
                "pending_email_change_id": self.pending_email_change.id,
                "token": self.token,
            },
        )

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
        self.assertEqual(
            response.context["form"].pending_email_change_id,
            self.pending_email_change.id,
        )
        self.assertEqual(response.context["form"].token, self.token)

    def test_post_anonymous_user_redirects_to_login(self):
        response = self.client.post(self.url)

        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    @patch("users.views.email.change_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_post_valid_token_changes_email(self, mock_check_token, mock_change_email):
        mock_check_token.return_value = True

        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("email-change"))
        mock_check_token.assert_called_once_with(self.user, self.token)
        mock_change_email.assert_called_once_with(
            user_id=self.user.id, pending_email_change_id=self.pending_email_change.id
        )

    @patch("users.views.email.change_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_post_invalid_token_shows_form_error(
        self, mock_check_token, mock_change_email
    ):
        mock_check_token.return_value = False

        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].token, self.token)
        self.assertFormError(response.context["form"], None, "Invalid token.")
        mock_check_token.assert_called_once_with(self.user, self.token)
        mock_change_email.assert_not_called()

    @patch("users.views.email.change_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_post_without_pending_email_change_shows_form_error(
        self, mock_check_token, mock_change_email
    ):
        self.pending_email_change.delete()

        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].token, self.token)
        self.assertFormError(
            response.context["form"],
            None,
            "This email change request no longer exists.",
        )
        mock_check_token.assert_not_called()
        mock_change_email.assert_not_called()

    @patch("users.views.email.change_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_post_pending_email_change_for_another_user_shows_form_error(
        self, mock_check_token, mock_change_email
    ):
        other_user = User.objects.create_user(
            username="otheruser", email="other@test.com"
        )
        other_pending_email_change = PendingEmailChange.objects.create(
            user=other_user, email="other-pending@test.com"
        )
        url = reverse(
            "email-change-confirm",
            kwargs={
                "pending_email_change_id": other_pending_email_change.id,
                "token": self.token,
            },
        )

        self.client.force_login(self.user)

        response = self.client.post(url, {"token": self.token})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].token, self.token)
        self.assertFormError(
            response.context["form"],
            None,
            "This email change request no longer exists.",
        )
        mock_check_token.assert_not_called()
        mock_change_email.assert_not_called()

    @patch("users.views.email.change_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_post_service_validation_error_shows_form_error(
        self, mock_check_token, mock_change_email
    ):
        from django.core.exceptions import ValidationError

        mock_check_token.return_value = True
        mock_change_email.side_effect = ValidationError(
            "This email address is no longer available."
        )

        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertFormError(
            response.context["form"], None, "This email address is no longer available."
        )
        mock_check_token.assert_called_once_with(self.user, self.token)
        mock_change_email.assert_called_once_with(
            user_id=self.user.id, pending_email_change_id=self.pending_email_change.id
        )
