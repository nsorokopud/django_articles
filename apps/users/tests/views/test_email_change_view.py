from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestEmailChangeView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("email-change")
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

    def test_get_anonymous_user(self):
        response = self.client.get(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'

        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_get_logged_in_user_without_pending_email(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change.html")
        self.assertEqual(response.context["form"].user, self.user)
        self.assertIsNone(response.context["pending_email"])

    def test_get_logged_in_user_with_pending_email(self):
        pending_email = EmailAddress.objects.create(
            user=self.user, email="pending@test.com", primary=False, verified=False
        )

        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change.html")
        self.assertEqual(response.context["form"].user, self.user)
        self.assertEqual(response.context["pending_email"], pending_email)

    def test_post_anonymous_user(self):
        response = self.client.post(self.url, {"new_email": "new@test.com"})
        redirect_url = f'{reverse("login")}?next={self.url}'

        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    @patch("users.views.email.send_email_change_link")
    def test_post_invalid_data(self, mock_send_email):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change.html")
        self.assertFalse(response.context["form"].is_valid())
        mock_send_email.assert_not_called()

        self.assertFalse(
            EmailAddress.objects.filter(
                user=self.user, primary=False, verified=False
            ).exists()
        )

    @patch("users.views.email.send_email_change_link")
    def test_post_valid_data(self, mock_send_email):
        data = {"new_email": "New@Test.COM"}

        self.client.force_login(self.user)
        response = self.client.post(self.url, data)

        self.assertRedirects(
            response, self.url, status_code=302, target_status_code=200
        )

        pending_email = EmailAddress.objects.get(
            user=self.user, primary=False, verified=False
        )

        self.assertEqual(pending_email.email, "new@test.com")
        mock_send_email.assert_called_once_with(
            self.user,
            pending_email.email,
            response.wsgi_request.build_absolute_uri("/"),
        )

    @patch("users.views.email.send_email_change_link")
    def test_post_same_email_as_current_user_email(self, mock_send_email):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"new_email": "USER@Test.COM"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change.html")
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("new_email", response.context["form"].errors)
        self.assertEqual(
            response.context["form"].errors["new_email"][0],
            "Enter a different email address.",
        )
        mock_send_email.assert_not_called()

        self.assertFalse(
            EmailAddress.objects.filter(
                user=self.user, primary=False, verified=False
            ).exists()
        )

    @patch("users.views.email.send_email_change_link")
    def test_post_when_pending_email_already_exists(self, mock_send_email):
        EmailAddress.objects.create(
            user=self.user, email="pending@test.com", primary=False, verified=False
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, {"new_email": "another@test.com"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change.html")
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("__all__", response.context["form"].errors)
        self.assertEqual(
            response.context["form"].errors["__all__"][0],
            (
                "There is an unfinished email address change process. "
                "Cancel it to start a new one."
            ),
        )
        mock_send_email.assert_not_called()

        self.assertEqual(
            EmailAddress.objects.filter(
                user=self.user, primary=False, verified=False
            ).count(),
            1,
        )

    @patch("users.views.email.create_pending_email_address")
    @patch("users.views.email.send_email_change_link")
    def test_post_service_validation_error_is_added_to_form(
        self, mock_send_email, mock_create_pending_email_address
    ):
        mock_create_pending_email_address.side_effect = ValidationError(
            "There is already a pending email change."
        )

        self.client.force_login(self.user)

        response = self.client.post(self.url, {"new_email": "new@test.com"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_change.html")
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("__all__", response.context["form"].errors)
        self.assertEqual(
            response.context["form"].errors["__all__"][0],
            "There is already a pending email change.",
        )

        mock_create_pending_email_address.assert_called_once_with(
            user_id=self.user.id, email="new@test.com"
        )
        mock_send_email.assert_not_called()
