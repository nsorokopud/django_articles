from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()

    def test_user_registration_view_get(self):
        response = self.client.get(reverse("registration"))
        self.assertEquals(response.status_code, 200)
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
        self.assertEquals(user.username, user_data["username"])

    def test_user_login_view_get(self):
        response = self.client.get(reverse("login"))
        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed("users/login.html")

    def test_user_login_view_post(self):
        login_data = {"username": "test_user", "password": "12345"}

        response = self.client.get("login")
        self.assertEquals(response.wsgi_request.user.is_authenticated, False)

        response = self.client.post(reverse("login"), login_data)
        self.assertRedirects(response, reverse("home"), status_code=302, target_status_code=200)
        self.assertEquals(response.wsgi_request.user.is_authenticated, True)
        self.assertEquals(response.wsgi_request.user, self.test_user)

    def test_user_logout_view_get(self):
        response = self.client.get(reverse("logout"))
        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed("users/logout.html")

    def test_user_logout_view_post(self):
        self.client.login(username="test_user", password="12345")

        response = self.client.get(reverse("registration"))
        self.assertEquals(response.wsgi_request.user.is_authenticated, True)
        response = self.client.post(reverse("logout"))
        self.assertEquals(response.wsgi_request.user.is_authenticated, False)

        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed("users/logout.html")