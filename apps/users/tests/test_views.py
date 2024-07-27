from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from users.models import Profile


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()
        self.test_user_profile = Profile.objects.create(user=self.test_user)

    def test_user_registration_view_get(self):
        response = self.client.get(reverse("registration"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("users/registration.html")

    def test_user_registration_view_post(self):
        user_data = {
            "username": "user1",
            "email": "aa1@gmail.com",
            "password1": "asdasab1231",
            "password2": "asdasab1231",
        }

        response = self.client.post(reverse("registration"), user_data)
        self.assertRedirects(response, reverse("login"), status_code=302, target_status_code=200)
        user = User.objects.order_by("id").last()
        self.assertEqual(user.username, user_data["username"])

    def test_user_login_view_get(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("users/login.html")

    def test_user_login_view_post(self):
        login_data = {"username": "test_user", "password": "12345"}

        response = self.client.get("login")
        self.assertEqual(response.wsgi_request.user.is_authenticated, False)

        response = self.client.post(reverse("login"), login_data)
        self.assertRedirects(response, reverse("home"), status_code=302, target_status_code=200)
        self.assertEqual(response.wsgi_request.user.is_authenticated, True)
        self.assertEqual(response.wsgi_request.user, self.test_user)

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
        self.assertTemplateUsed("users/logout.html")

    def test_user_profile_view(self):
        response = self.client.get(reverse("user-profile"))
        redirect_url = f'{reverse("login")}?next={reverse("user-profile")}'
        self.assertRedirects(response, redirect_url, status_code=302, target_status_code=200)

        self.client.login(username="test_user", password="12345")
        response = self.client.get(reverse("user-profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("users/profile.html")
