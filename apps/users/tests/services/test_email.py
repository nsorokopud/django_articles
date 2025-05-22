from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.services import User, send_account_activation_email, send_email_change_link


class TestEmailServices(TestCase):

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_send_account_activation_email(self):
        html_template = (
            "Hello, {username}.\n  <br>\n  <br>\n"
            "  Please follow the link to finish your registration:\n"
            '  <a href="{url}">'
            "Finish registration</a>"
        )
        plain_template = (
            "Hello, {username}.\n\nPlease follow the link to finish your registration:"
            "\n{url}"
        )

        user1 = User.objects.create_user(username="user1", email="user1@test.com")
        user2 = User.objects.create_user(username="user2", email="user2@test.com")

        self.assertEqual(len(mail.outbox), 0)

        factory = RequestFactory()
        request = factory.get(reverse("post-registration"), secure=True)
        request.META["HTTP_HOST"] = "testserver"
        request.user = user1

        with patch(
            "users.services.tokens.activation_token_generator.make_token",
            return_value="token1",
        ):
            send_account_activation_email(request, user1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ["user1@test.com"])
        self.assertEqual(mail.outbox[0].subject, "User account activation")
        uid = urlsafe_base64_encode(force_bytes(user1.pk))
        expected_url = f"https://testserver/activate_account/{uid}/token1/"
        self.assertEqual(
            mail.outbox[0].alternatives[0][0],
            html_template.format(username=user1.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[0].body,
            plain_template.format(username=user1.username, url=expected_url),
        )
        self.assertEqual(len(mail.outbox[0].alternatives), 1)

        request = factory.get(reverse("post-registration"), secure=False)
        request.META["HTTP_HOST"] = "testserver"
        request.user = user2

        with patch(
            "users.services.tokens.activation_token_generator.make_token",
            return_value="token2",
        ):
            send_account_activation_email(request, user2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].recipients(), ["user2@test.com"])
        uid = urlsafe_base64_encode(force_bytes(user2.pk))
        expected_url = f"http://testserver/activate_account/{uid}/token2/"
        self.assertEqual(
            mail.outbox[1].alternatives[0][0],
            html_template.format(username=user2.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[1].body,
            plain_template.format(username=user2.username, url=expected_url),
        )
        self.assertEqual(len(mail.outbox[1].alternatives), 1)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_send_email_change_link(self):
        html_template = (
            "Hello, {username}.\n  <br>\n  <br>\n"
            "  Please follow the link to confirm this email address as your new one:\n"
            '  <a href="{url}">'
            "Change email</a>"
        )
        plain_template = (
            "Hello, {username}.\n\nPlease follow the link to confirm this "
            "email address as your new one:\n{url}"
        )

        user1 = User.objects.create_user(username="user1", email="user1@test.com")
        user2 = User.objects.create_user(username="user2", email="user2@test.com")

        factory = RequestFactory()
        request = factory.get(
            reverse("email-change-confirm", args=["token1"]), secure=True
        )
        request.META["HTTP_HOST"] = "testserver"

        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            send_email_change_link(request, user1)
        self.assertEqual(len(mail.outbox), 0)

        request.user = user1
        with patch(
            "users.services.tokens.email_change_token_generator.make_token",
            return_value="token1",
        ):
            send_email_change_link(request, "u1@test.com")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ["u1@test.com"])
        self.assertEqual(mail.outbox[0].subject, "Confirm email change")
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        expected_url = "https://testserver/confirm_email_change/token1/"
        self.assertEqual(
            mail.outbox[0].alternatives[0][0],
            html_template.format(username=user1.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[0].body,
            plain_template.format(username=user1.username, url=expected_url),
        )

        request = factory.get(
            reverse("email-change-confirm", args=["token2"]), secure=False
        )
        request.META["HTTP_HOST"] = "testserver"
        request.user = user2

        with patch(
            "users.services.tokens.email_change_token_generator.make_token",
            return_value="token2",
        ):
            send_email_change_link(request, "u2@test.com")

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].recipients(), ["u2@test.com"])
        expected_url = "http://testserver/confirm_email_change/token2/"
        self.assertEqual(
            mail.outbox[1].alternatives[0][0],
            html_template.format(username=user2.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[1].body,
            plain_template.format(username=user2.username, url=expected_url),
        )
