from unittest.mock import ANY, call, patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.forms import AuthenticationForm
from users.models import User
from users.tokens import activation_token_generator


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

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True), patch(
            "users.views.send_account_activation_email"
        ) as send_email__mock:
            response = self.client.post(reverse("registration"), user_data)
            user = User.objects.order_by("id").last()
            self.assertEqual(user.username, user_data["username"])
            self.assertFalse(user.is_active)
            self.assertCountEqual(send_email__mock.call_args_list, [call(ANY, user)])

        self.assertRedirects(
            response, reverse("post-registration"), status_code=302, target_status_code=200
        )

    def test_post_registration_view(self):
        response = self.client.get(reverse("post-registration"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/post_registration.html")

        response = self.client.post(reverse("post-registration"))
        self.assertEqual(response.status_code, 405)

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
        self.assertRedirects(
            response, reverse("articles"), status_code=302, target_status_code=200
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user, self.test_user)

        self.client.logout()

        with patch("hcaptcha_field.hCaptchaField.validate", return_value=True):
            response = self.client.post(reverse("login"), login_data2)
        self.assertRedirects(
            response, reverse("articles"), status_code=302, target_status_code=200
        )
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
        self.assertEqual(
            form.errors,
            {
                "__all__": [
                    "Please enter a correct username and password. Note that both fields may be case-sensitive."
                ]
            },
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotEqual(response.wsgi_request.user, self.test_user)

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

        redirect_url = f"{reverse('login')}?next={target_url}"
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

    def test_account_activation_view(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="a12345", is_active=False
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="b12345", is_active=False
        )
        user3 = User.objects.create_user(
            username="user3", email="user3@test.com", password="c12345", is_active=True
        )

        self.assertFalse(user1.is_active)
        self.assertFalse(user2.is_active)
        self.assertTrue(user3.is_active)

        user1_encoded_id = urlsafe_base64_encode(force_bytes(user1.pk))
        token1 = activation_token_generator.make_token(user1)
        token2 = activation_token_generator.make_token(user2)

        # correct case
        self.client.force_login(user3)
        response = self.client.get(reverse("account-activate", args=[user1_encoded_id, token1]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertTrue(response.context["is_activation_successful"])
        with self.assertRaises(KeyError):
            response.context["error_message"]
        user1.refresh_from_db()
        user2.refresh_from_db()
        self.assertTrue(user1.is_active)
        self.assertFalse(user2.is_active)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertTrue(response.context["user"].is_anonymous)

        # trying to activate already activated account
        response = self.client.get(reverse("account-activate", args=[user1_encoded_id, token1]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(response.context["error_message"], "This account is already activated")
        user1.refresh_from_db()
        self.assertTrue(user1.is_active)

        user1.is_active = False
        user1.save()

        # invalid user_id
        response = self.client.get(reverse("account-activate", args=["abc", token1]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(response.context["error_message"], "Invalid user id")
        user1.refresh_from_db()
        user2.refresh_from_db()
        self.assertFalse(user1.is_active)
        self.assertFalse(user2.is_active)

        # unencoded user_id
        response = self.client.get(reverse("account-activate", args=[user1.id, token1]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(response.context["error_message"], "Invalid user id")
        user1.refresh_from_db()
        user2.refresh_from_db()
        self.assertFalse(user1.is_active)
        self.assertFalse(user2.is_active)

        # non-existent user_id
        nonexistent_user_id = urlsafe_base64_encode(force_bytes(-1))
        response = self.client.get(reverse("account-activate", args=[nonexistent_user_id, token1]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(response.context["error_message"], "Invalid user id")
        user1.refresh_from_db()
        self.assertFalse(user1.is_active)

        # invalid token
        response = self.client.get(reverse("account-activate", args=[user1_encoded_id, token2]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(response.context["error_message"], "Invalid token")
        user1.refresh_from_db()
        user2.refresh_from_db()
        self.assertFalse(user1.is_active)
        self.assertFalse(user1.is_active)

    def test_password_set_view_get(self):
        url = reverse("password-set")

        # anonymous user
        response = self.client.get(url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)

        # user with usable password
        self.client.force_login(self.test_user)
        response = self.client.get(url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)

        # user without usable password
        user = User.objects.create_user(username="user1", email="user1@test.com")
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_set.html")

    def test_password_set_view_post(self):
        user = User.objects.create_user(username="user1", email="user1@test.com")
        password = "Abcd1234!"
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.check_password(password))

        url = reverse("password-set")

        # anonymous user
        response = self.client.post(
            url,
            {
                "password1": password,
                "password2": password,
            },
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)

        # user with usable password
        self.client.force_login(self.test_user)
        response = self.client.post(
            url,
            {
                "password1": password,
                "password2": password,
            },
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.test_user.check_password("12345"))

        # user without usable password
        self.client.force_login(user)
        response = self.client.post(
            url,
            {
                "password1": password,
                "password2": password,
            },
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(
            response, reverse("articles"), status_code=302, target_status_code=200
        )
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password(password))
