from django.test import TestCase
from django.urls import reverse, resolve

from users.views import UserRegistrationView, UserLoginView


class TestViews(TestCase):
    def test_user_registration_url_is_resolved(self):
        url = reverse("registration")
        self.assertEquals(resolve(url).func.view_class, UserRegistrationView)

    def test_user_login_url_is_resolved(self):
        url = reverse("login")
        self.assertEquals(resolve(url).func.view_class, UserLoginView)
