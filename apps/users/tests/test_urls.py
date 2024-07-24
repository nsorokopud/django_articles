from django.test import TestCase
from django.urls import reverse, resolve

from users.views import UserLoginView, UserLogoutView, UserProfileView, UserRegistrationView


class TestURLs(TestCase):
    def test_user_registration_url_is_resolved(self):
        url = reverse("registration")
        self.assertEqual(resolve(url).func.view_class, UserRegistrationView)

    def test_user_login_url_is_resolved(self):
        url = reverse("login")
        self.assertEqual(resolve(url).func.view_class, UserLoginView)

    def test_user_logout_url_is_resolved(self):
        url = reverse("logout")
        self.assertEqual(resolve(url).func.view_class, UserLogoutView)

    def test_user_profile_url_is_resolved(self):
        url = reverse("user-profile")
        self.assertEqual(resolve(url).func.view_class, UserProfileView)
