from unittest.mock import patch

from django.contrib.auth import SESSION_KEY
from django.core.exceptions import ValidationError
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
                "pending_email_change_public_id": self.pending_email_change.public_id,
                "token": self.token,
            },
        )

    def test_get_anonymous_user_renders_confirmation_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(
            response.context["form"].pending_email_change_public_id,
            self.pending_email_change.public_id,
        )
        self.assertEqual(response.context["form"].token, self.token)

    def test_get_authenticated_user_renders_confirmation_form(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(
            response.context["form"].pending_email_change_public_id,
            self.pending_email_change.public_id,
        )
        self.assertEqual(response.context["form"].token, self.token)

    @patch("users.views.email.change_email_address")
    def test_post_anonymous_valid_link_calls_service_and_redirects_to_login(
        self, mock_change_email
    ):
        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("login"))
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )

    @patch("users.views.email.change_email_address")
    def test_post_logged_in_valid_link_calls_service_logs_out_and_redirects_to_login(
        self, mock_change_email
    ):
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("login"))
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )
        self.assertNotIn(SESSION_KEY, self.client.session)

    @patch("users.views.email.change_email_address")
    def test_post_uses_pending_email_change_user_not_logged_in_user(
        self, mock_change_email
    ):
        other_user = User.objects.create_user(
            username="otheruser", email="other@test.com"
        )
        self.client.force_login(other_user)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("login"))
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )
        self.assertNotIn(SESSION_KEY, self.client.session)

    @patch("users.views.email.change_email_address")
    def test_post_service_invalid_token_error_shows_generic_form_error(
        self, mock_change_email
    ):
        mock_change_email.side_effect = ValidationError("Invalid email change link.")

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].token, self.token)
        self.assertEqual(
            response.context["form"].pending_email_change_public_id,
            self.pending_email_change.public_id,
        )
        self.assertFormError(
            response.context["form"],
            None,
            "This email change link is invalid or has expired.",
        )
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )

    @patch("users.views.email.change_email_address")
    def test_post_service_missing_pending_email_change_error_shows_generic_form_error(
        self, mock_change_email
    ):
        mock_change_email.side_effect = ValidationError(
            "This email change request no longer exists."
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertFormError(
            response.context["form"],
            None,
            "This email change link is invalid or has expired.",
        )
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )

    @patch("users.views.email.change_email_address")
    def test_post_service_validation_error_shows_generic_form_error(
        self, mock_change_email
    ):
        mock_change_email.side_effect = ValidationError(
            "This email address is no longer available."
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertFormError(
            response.context["form"],
            None,
            "This email change link is invalid or has expired.",
        )
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )

    @patch("users.views.email.change_email_address")
    def test_post_missing_pending_email_change_row_shows_generic_form_error(
        self, mock_change_email
    ):
        self.pending_email_change.delete()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertFormError(
            response.context["form"],
            None,
            "This email change link is invalid or has expired.",
        )
        mock_change_email.assert_not_called()
