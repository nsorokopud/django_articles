# pylint: disable=assignment-from-no-return

from types import SimpleNamespace
from unittest.mock import patch

from allauth.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from users.adapters import AccountAdapter, SocialAccountAdapter


User = get_user_model()


def add_messages_middleware_support(request):
    """Allows django.contrib.messages to work on RequestFactory requests."""
    request.session = {}
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)
    return request


class TestAccountAdapter(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = AccountAdapter()

    def test_get_password_change_redirect_url_returns_profile_url(self):
        request = self.factory.get("/")

        url = self.adapter.get_password_change_redirect_url(request)

        self.assertEqual(url, reverse("user-profile"))

    def test_get_login_redirect_url_redirects_user_without_usable_password(self):
        user = User.objects.create_user(
            username="googleuser", email="google@test.com", password=None
        )

        request = self.factory.get("/")
        request.user = user

        url = self.adapter.get_login_redirect_url(request)

        self.assertEqual(url, reverse("password-set"))

    @override_settings(LOGIN_REDIRECT_URL="/articles/")
    def test_get_login_redirect_url_uses_default_for_user_with_usable_password(self):
        user = User.objects.create_user(
            username="regularuser",
            email="regular@test.com",
            password="strong-test-password",
        )

        request = self.factory.get("/")
        request.user = user

        url = self.adapter.get_login_redirect_url(request)

        self.assertEqual(url, "/articles/")

    def test_get_signup_redirect_url_delegates_to_login_redirect_url(self):
        user = User.objects.create_user(
            username="socialuser", email="social@test.com", password=None
        )

        request = self.factory.get("/")
        request.user = user

        url = self.adapter.get_signup_redirect_url(request)

        self.assertEqual(url, reverse("password-set"))


class TestSocialAccountAdapter(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = SocialAccountAdapter()

    def build_request(self):
        request = self.factory.get("/accounts/google/login/callback/")
        return add_messages_middleware_support(request)

    def build_sociallogin(
        self,
        *,
        provider="google",
        user_email="person@test.com",
        extra_email="person@test.com",
        email_verified=True,
    ):
        return SimpleNamespace(
            user=SimpleNamespace(email=user_email),
            account=SimpleNamespace(
                provider=provider,
                extra_data={"email": extra_email, "email_verified": email_verified},
            ),
        )

    def assert_rejected(self, sociallogin):
        request = self.build_request()

        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(request, sociallogin)

        response = ctx.exception.response
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

    def test_pre_social_login_allows_verified_google_account_with_matching_email(self):
        request = self.build_request()
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email="person@test.com",
            extra_email="person@test.com",
            email_verified=True,
        )

        result = self.adapter.pre_social_login(request, sociallogin)

        self.assertIsNone(result)

    def test_pre_social_login_normalizes_email_case_and_whitespace(self):
        request = self.build_request()
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email=" Person@Example.COM ",
            extra_email=" person@example.com ",
            email_verified=True,
        )

        result = self.adapter.pre_social_login(request, sociallogin)

        self.assertIsNone(result)

    def test_pre_social_login_rejects_non_google_provider(self):
        sociallogin = self.build_sociallogin(
            provider="github",
            user_email="person@test.com",
            extra_email="person@test.com",
            email_verified=True,
        )

        self.assert_rejected(sociallogin)

    def test_pre_social_login_rejects_missing_extra_data(self):
        sociallogin = SimpleNamespace(
            user=SimpleNamespace(email="person@test.com"),
            account=SimpleNamespace(provider="google", extra_data=None),
        )

        self.assert_rejected(sociallogin)

    def test_pre_social_login_rejects_missing_sociallogin_user_email(self):
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email="",
            extra_email="person@test.com",
            email_verified=True,
        )

        self.assert_rejected(sociallogin)

    def test_pre_social_login_rejects_missing_google_email(self):
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email="person@test.com",
            extra_email="",
            email_verified=True,
        )

        self.assert_rejected(sociallogin)

    def test_pre_social_login_rejects_unverified_google_email(self):
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email="person@test.com",
            extra_email="person@test.com",
            email_verified=False,
        )

        self.assert_rejected(sociallogin)

    def test_pre_social_login_rejects_missing_email_verified_flag(self):
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email="person@test.com",
            extra_email="person@test.com",
            email_verified=None,
        )

        self.assert_rejected(sociallogin)

    def test_pre_social_login_rejects_truthy_string_email_verified_flag(self):
        """
        The adapter requires `email_verified is True`, not just truthy.
        This protects against provider payload shape changes.
        """
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email="person@test.com",
            extra_email="person@test.com",
            email_verified="true",
        )

        self.assert_rejected(sociallogin)

    def test_pre_social_login_rejects_email_mismatch(self):
        sociallogin = self.build_sociallogin(
            provider="google",
            user_email="person@test.com",
            extra_email="other@test.com",
            email_verified=True,
        )

        self.assert_rejected(sociallogin)

    @patch("users.adapters.messages.error")
    def test_rejection_adds_message_for_non_google_provider(self, mock_error):
        request = self.build_request()
        sociallogin = self.build_sociallogin(provider="github")

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

        mock_error.assert_called_once_with(
            request, "Unsupported social login provider."
        )

    @patch("users.adapters.messages.error")
    def test_rejection_adds_message_for_unverified_google_email(self, mock_error):
        request = self.build_request()
        sociallogin = self.build_sociallogin(email_verified=False)

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

        mock_error.assert_called_once_with(
            request, "Your Google email address is not verified."
        )

    @patch("users.adapters.messages.error")
    def test_rejection_adds_message_for_missing_email(self, mock_error):
        request = self.build_request()
        sociallogin = self.build_sociallogin(
            user_email="", extra_email="person@test.com", email_verified=True
        )

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

        mock_error.assert_called_once_with(
            request, "Google did not provide an email address."
        )

    @patch("users.adapters.messages.error")
    def test_rejection_adds_message_for_email_mismatch(self, mock_error):
        request = self.build_request()
        sociallogin = self.build_sociallogin(
            user_email="person@test.com",
            extra_email="other@test.com",
            email_verified=True,
        )

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

        mock_error.assert_called_once_with(request, "Google account email mismatch.")
