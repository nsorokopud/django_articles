from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestPasswordChangeView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("password-change")
        self.old_password = "Abcd1234"
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password=self.old_password
        )

    def test_get_anonymous_user(self):
        response = self.client.get(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_get_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_change.html")
        self.assertEqual(response.context["form"].user, self.user)

    def test_post_anonymous_user(self):
        response = self.client.post(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_post_invalid_data(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertTrue(self.user.check_password("Abcd1234"))

    def test_post_valid_data(self):
        new_password = "Abcd1234!"
        data = {
            "oldpassword": self.old_password,
            "password1": new_password,
            "password2": new_password,
        }
        self.assertTrue(self.user.check_password(self.old_password))

        self.client.force_login(self.user)
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("user-profile"))

        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.old_password))
        self.assertTrue(self.user.check_password(new_password))
