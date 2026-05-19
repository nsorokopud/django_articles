from unittest.mock import patch

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
    def test_post_valid_link_calls_service_and_redirects(self, mock_change_email):
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("email-change"))
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )

    @patch("users.views.email.change_email_address")
    def test_post_service_invalid_token_error_shows_form_error(self, mock_change_email):
        mock_change_email.side_effect = ValidationError("Invalid email change link.")

        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertEqual(response.context["form"].token, self.token)
        self.assertFormError(
            response.context["form"], None, "Invalid email change link."
        )
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )

    @patch("users.views.email.change_email_address")
    def test_post_service_missing_pending_email_change_error_shows_form_error(
        self, mock_change_email
    ):
        mock_change_email.side_effect = ValidationError(
            "This email change request no longer exists."
        )

        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change_confirm.html")
        self.assertFormError(
            response.context["form"],
            None,
            "This email change request no longer exists.",
        )
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )

    @patch("users.views.email.change_email_address")
    def test_post_service_validation_error_shows_form_error(self, mock_change_email):
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
        mock_change_email.assert_called_once_with(
            user_id=self.user.id,
            pending_email_change_id=self.pending_email_change.id,
            token=self.token,
        )
