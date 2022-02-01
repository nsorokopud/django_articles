from django.test import TestCase
from django.urls import reverse, resolve

from users.views import UserRegistrationView


class TestViews(TestCase):
    def test_user_registration_url_is_resolved(self):
        url = reverse("registration")
        self.assertEquals(resolve(url).func.view_class, UserRegistrationView)
