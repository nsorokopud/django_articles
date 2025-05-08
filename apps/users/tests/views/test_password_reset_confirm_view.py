from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import User
from users.services.tokens import password_reset_token_generator


class TestPasswordResetConfirmView(TestCase):
    def setUp(self):
        self.client = Client()
        self.old_password = "Abcd1234"
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password=self.old_password
        )

    def test_get_invalid_token(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        url = reverse("password_reset_confirm", args=[uidb64, "123"])
        self.assertTrue(password_reset_token_generator.check_token(self.user, token))

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_reset_confirm.html")
        self.assertFalse(response.context["validlink"])

    def test_get_valid_token(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        url = reverse("password_reset_confirm", args=[uidb64, token])
        self.assertTrue(password_reset_token_generator.check_token(self.user, token))

        response = self.client.get(url, follow=True)
        self.assertRedirects(
            response,
            reverse("password_reset_confirm", args=[uidb64, "set-password"]),
            status_code=302,
            target_status_code=200,
        )
        self.assertTemplateUsed(response, "users/password_reset_confirm.html")
        self.assertTrue(response.context["validlink"])

    def test_get_logged_in_user(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        url = reverse("password_reset_confirm", args=[uidb64, token])
        self.assertTrue(password_reset_token_generator.check_token(self.user, token))

        self.client.force_login(self.user)
        response = self.client.get(url, follow=True)
        self.assertTemplateUsed(response, "users/password_reset_confirm.html")
        self.assertFalse(response.context["validlink"])

    def test_post_invalid_data(self):
        data = {
            "new_password1": "abc",
            "new_password2": "123",
        }
        self.assertTrue(self.user.check_password(self.old_password))

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        url = reverse("password_reset_confirm", args=[uidb64, token])

        get_response = self.client.get(url, follow=True)
        final_url = get_response.redirect_chain[-1][0]

        post_response = self.client.post(final_url, data, follow=True)
        self.assertEqual(post_response.status_code, 200)
        self.assertTemplateUsed(post_response, "users/password_reset_confirm.html")
        self.assertTrue(post_response.context["validlink"])
        self.assertFalse(post_response.context["form"].is_valid())
        self.assertEqual(
            post_response.context["form"].errors,
            {"new_password2": ["The two password fields didn’t match."]},
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_post_valid_data(self):
        new_password = "Abcd1234!"
        data = {
            "new_password1": new_password,
            "new_password2": new_password,
        }
        self.assertTrue(self.user.check_password(self.old_password))

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        url = reverse("password_reset_confirm", args=[uidb64, token])

        get_response = self.client.get(url, follow=True)
        final_url = get_response.redirect_chain[-1][0]

        post_response = self.client.post(final_url, data, follow=True)
        self.assertRedirects(
            post_response,
            reverse("login"),
            status_code=302,
            target_status_code=200,
        )

        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.old_password))
        self.assertTrue(self.user.check_password(new_password))
