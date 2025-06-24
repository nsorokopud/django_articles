from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestPasswordSetView(TestCase):
    def setUp(self):
        self.client = Client()

        self.url = reverse("password-set")
        self.user = User.objects.create_user(username="user", email="test@test.com")
        self.password = "Abcd1234!"
        self.form_data = {
            "password1": self.password,
            "password2": self.password,
        }

    def test_get_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "error.html")

    def test_get_unusable_password(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_set.html")

    def test_get_usable_password(self):
        self.user.set_password("12345")
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "error.html")

    def test_post_anonymous_user(self):
        response = self.client.post(self.url, self.form_data)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "error.html")

    def test_post_usable_password(self):
        self.user.set_password("12345")
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.post(self.url, self.form_data)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "error.html")
        self.assertTrue(self.user.check_password("12345"))

    def test_post_unusable_password(self):
        self.assertFalse(self.user.has_usable_password())
        self.assertFalse(self.user.check_password(self.password))

        self.client.force_login(self.user)
        response = self.client.post(self.url, self.form_data)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(
            response, reverse("user-profile"), status_code=302, target_status_code=200
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_usable_password())
        self.assertTrue(self.user.check_password(self.password))
