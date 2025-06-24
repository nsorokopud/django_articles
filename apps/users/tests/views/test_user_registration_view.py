from unittest.mock import call, patch

from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestUserRegistrationView(TestCase):
    def setUp(self):
        self.client = Client()

    def test_get(self):
        response = self.client.get(reverse("registration"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/registration.html")

    def test_post(self):
        user_data = {
            "username": "user1",
            "email": "user1@test.com",
            "password1": "asdasab1231",
            "password2": "asdasab1231",
        }

        invalid_user_data = {
            "username": "user1",
            "email": "user1@test",
            "password1": "asdasab1231",
            "password2": "123",
        }

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("registration"), invalid_user_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("users/registration.html")
        self.assertEqual(
            response.context["form"].errors,
            {
                "email": ["Enter a valid email address."],
                "password2": ["The two password fields didn’t match."],
            },
        )

        with (
            patch("hcaptcha_field.hCaptchaField.validate", return_value=True),
            patch(
                "users.views.registration.send_account_activation_email"
            ) as send_email__mock,
        ):
            response = self.client.post(reverse("registration"), user_data)
            user = User.objects.get(username=user_data["username"])
            self.assertFalse(user.is_active)
            self.assertCountEqual(
                send_email__mock.call_args_list,
                [call(user, response.wsgi_request.build_absolute_uri("/"))],
            )

            # Ensure user object is deactivated before making token
            # (otherwise token will get invalidated)
            args = send_email__mock.call_args_list[0][0]
            passed_user = args[0]
            self.assertFalse(passed_user.is_active)

        self.assertRedirects(
            response,
            reverse("post-registration"),
            status_code=302,
            target_status_code=200,
        )
