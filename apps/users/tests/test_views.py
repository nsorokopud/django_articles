from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from users.forms import AuthenticationForm
from users.models import User


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()

    def test_user_registration_view_get(self):
        response = self.client.get(reverse("registration"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/registration.html")

    def test_user_registration_view_post(self):
        user_data = {
            "username": "user1",
            "email": "aa1@gmail.com",
            "password1": "asdasab1231",
            "password2": "asdasab1231",
        }

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("registration"), user_data)
            self.assertRedirects(response, reverse("login"), status_code=302, target_status_code=200)
            user = User.objects.order_by("id").last()
            self.assertEqual(user.username, user_data["username"])

    def test_user_login_view_get(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/login.html")

    def test_user_login_view_post(self):
        login_data1 = {"username": "test_user", "password": "12345"}
        login_data2 = {"username": "test@test.com", "password": "12345"}
        login_data_invalid = {"username": "invalid", "password": "invalid"}

        response = self.client.get("login")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("login"), login_data1)
        self.assertRedirects(response, reverse("articles"), status_code=302, target_status_code=200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user, self.test_user)

        self.client.logout()

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("login"), login_data2)
        self.assertRedirects(response, reverse("articles"), status_code=302, target_status_code=200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user, self.test_user)

        self.client.logout()

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("login"), login_data_invalid)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/login.html")
        form = response.context["form"]
        self.assertTrue(isinstance(form, AuthenticationForm))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"__all__": [
            "Please enter a correct username and password. Note that both fields may be case-sensitive."
        ]})
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotEqual(response.wsgi_request.user, self.test_user)

    def test_user_logout_view_get(self):
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)

    def test_user_logout_view_post(self):
        self.client.login(username="test_user", password="12345")

        response = self.client.get(reverse("registration"))
        self.assertEqual(response.wsgi_request.user.is_authenticated, True)
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.wsgi_request.user.is_authenticated, False)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/logout.html")

    def test_user_profile_view(self):
        response = self.client.get(reverse("user-profile"))
        redirect_url = f'{reverse("login")}?next={reverse("user-profile")}'
        self.assertRedirects(response, redirect_url, status_code=302, target_status_code=200)

        self.client.login(username="test_user", password="12345")
        response = self.client.get(reverse("user-profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")

    def test_author_page_view(self):
        response = self.client.get(reverse("author-page", args=(self.test_user.username,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/author_page.html")

    def test_author_subscribe_view(self):
        author = User.objects.create_user(username="author1")

        target_url = reverse("author-subscribe", args=(author.username,))
        response = self.client.post(target_url)

        redirect_url = f"{reverse("login")}?next={target_url}"
        self.assertRedirects(response, redirect_url, status_code=302, target_status_code=200)

        self.client.force_login(self.test_user)
        self.assertTrue(self.test_user not in author.profile.subscribers.all())

        response = self.client.post(target_url)
        redirect_url = reverse("author-page", args=(author.username,))
        self.assertRedirects(response, redirect_url, status_code=302, target_status_code=200)
        self.assertTrue(self.test_user in author.profile.subscribers.all())

        response = self.client.post(target_url)
        redirect_url = reverse("author-page", args=(author.username,))
        self.assertRedirects(response, redirect_url, status_code=302, target_status_code=200)
        self.assertTrue(self.test_user not in author.profile.subscribers.all())
