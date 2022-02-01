from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

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
