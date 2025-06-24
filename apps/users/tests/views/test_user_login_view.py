from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from users.forms import AuthenticationForm
from users.models import User


class TestUserLoginView(TestCase):
    def setUp(self):
        self.client = Client()

    def test_get(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/login.html")

    def test_post(self):
        user = User.objects.create_user(username="user", email="test@test.com")
        user.set_password("12345")
        user.save()
        login_data1 = {"username": "user", "password": "12345"}
        login_data2 = {"username": "test@test.com", "password": "12345"}
        login_data_invalid = {"username": "invalid", "password": "invalid"}

        response = self.client.get("login")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("login"), login_data1)
        self.assertRedirects(
            response, reverse("articles"), status_code=302, target_status_code=200
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user, user)

        self.client.logout()

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("login"), login_data2)
        self.assertRedirects(
            response, reverse("articles"), status_code=302, target_status_code=200
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user, user)

        self.client.logout()

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("login"), login_data_invalid)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/login.html")
        form = response.context["form"]
        self.assertTrue(isinstance(form, AuthenticationForm))
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "__all__": [
                    (
                        "Please enter a correct username and password. "
                        "Note that both fields may be case-sensitive."
                    )
                ]
            },
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotEqual(response.wsgi_request.user, user)
