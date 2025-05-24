from allauth.account.views import LogoutView
from allauth.socialaccount.providers.google import views as google_views
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from users.views import (
    AccountActivationView,
    AuthorPageView,
    AuthorSubscribeView,
    EmailChangeCancelView,
    EmailChangeConfirmationView,
    EmailChangeResendView,
    EmailChangeView,
    PasswordChangeView,
    PasswordResetView,
    PasswordSetView,
    PostUserRegistrationView,
    UserLoginView,
    UserPasswordResetConfirmView,
    UserProfileView,
    UserRegistrationView,
)


class TestURLs(SimpleTestCase):
    def test_account_activation_url_is_resolved(self):
        url = reverse("account-activate", args=["a", "b"])
        self.assertEqual(resolve(url).func.view_class, AccountActivationView)

    def test_author_page_url_is_resolved(self):
        url = reverse("author-page", kwargs={"author_id": 1})
        self.assertEqual(resolve(url).func.view_class, AuthorPageView)

    def test_author_subscribe_url_is_resolved(self):
        url = reverse("author-subscribe", kwargs={"author_id": 1})
        self.assertEqual(resolve(url).func.view_class, AuthorSubscribeView)

    def test_email_change_cancel_url_is_resolved(self):
        url = reverse("email-change-cancel")
        self.assertEqual(resolve(url).func.view_class, EmailChangeCancelView)

    def test_email_change_resend_url_is_resolved(self):
        url = reverse("email-change-resend")
        self.assertEqual(resolve(url).func.view_class, EmailChangeResendView)

    def test_email_change_url_is_resolved(self):
        url = reverse("email-change")
        self.assertEqual(resolve(url).func.view_class, EmailChangeView)

    def test_email_change_confirmation_url_is_resolved(self):
        url = reverse("email-change-confirm", args=["token"])
        self.assertEqual(resolve(url).func.view_class, EmailChangeConfirmationView)

    def test_password_change_url_is_resolved(self):
        url = reverse("password-change")
        self.assertEqual(resolve(url).func.view_class, PasswordChangeView)

    def test_user_password_reset_confirm_url_is_resolved(self):
        url = reverse("password_reset_confirm", args=["uidb64", "token"])
        self.assertEqual(resolve(url).func.view_class, UserPasswordResetConfirmView)

    def test_password_reset_url_is_resolved(self):
        url = reverse("password-reset")
        self.assertEqual(resolve(url).func.view_class, PasswordResetView)

    def test_password_set_url_is_resolved(self):
        url = reverse("password-set")
        self.assertEqual(resolve(url).func.view_class, PasswordSetView)

    def test_post_user_registration_url_is_resolved(self):
        url = reverse("post-registration")
        self.assertEqual(resolve(url).func.view_class, PostUserRegistrationView)

    def test_user_registration_url_is_resolved(self):
        url = reverse("registration")
        self.assertEqual(resolve(url).func.view_class, UserRegistrationView)

    def test_user_login_url_is_resolved(self):
        url = reverse("login")
        self.assertEqual(resolve(url).func.view_class, UserLoginView)

    def test_google_login_by_token_url_is_resolved(self):
        url = reverse("google_login_by_token")
        self.assertEqual(resolve(url).func.view_class, google_views.LoginByTokenView)

    def test_user_logout_url_is_resolved(self):
        url = reverse("account_logout")
        self.assertEqual(resolve(url).func.view_class, LogoutView)

    def test_user_profile_url_is_resolved(self):
        url = reverse("user-profile")
        self.assertEqual(resolve(url).func.view_class, UserProfileView)
