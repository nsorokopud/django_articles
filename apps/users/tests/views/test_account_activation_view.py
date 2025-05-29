from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import User
from users.services.tokens import activation_token_generator


class TestAccountActivationView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user1 = User.objects.create_user(
            username="user1", email="user1@test.com", is_active=False
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@test.com", is_active=False
        )
        self.user1_encoded_id = urlsafe_base64_encode(force_bytes(self.user1.pk))
        self.token1 = activation_token_generator.make_token(self.user1)

    def test_correct_case(self):
        user3 = User.objects.create_user(username="user3", email="user3@test.com")
        self.client.force_login(user3)

        response = self.client.get(
            reverse("account-activate", args=[self.user1_encoded_id, self.token1]),
            follow=True,
        )
        self.assertRedirects(
            response, reverse("login"), status_code=302, target_status_code=200
        )
        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertTrue(self.user1.is_active)
        self.assertFalse(self.user2.is_active)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertTrue(response.context["user"].is_anonymous)

    def test_already_activated_account(self):
        response = self.client.get(
            reverse("account-activate", args=[self.user1_encoded_id, self.token1])
        )
        self.assertRedirects(
            response, reverse("login"), status_code=302, target_status_code=200
        )
        self.user1.refresh_from_db()
        self.assertTrue(self.user1.is_active)

    def test_invalid_user_id(self):
        self.user1.is_active = False
        self.user1.save()
        response = self.client.get(
            reverse("account-activate", args=["abc", self.token1])
        )
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(
            response.context["error_message"],
            "The activation link is invalid or has expired",
        )
        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertFalse(self.user1.is_active)
        self.assertFalse(self.user2.is_active)

    def test_unencoded_user_id(self):
        response = self.client.get(
            reverse("account-activate", args=[self.user1.id, self.token1])
        )
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(
            response.context["error_message"],
            "The activation link is invalid or has expired",
        )
        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertFalse(self.user1.is_active)
        self.assertFalse(self.user2.is_active)

    def test_non_existent_user_id(self):
        nonexistent_user_id = urlsafe_base64_encode(force_bytes(-1))
        response = self.client.get(
            reverse("account-activate", args=[nonexistent_user_id, self.token1])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "error.html")
        self.user1.refresh_from_db()
        self.assertFalse(self.user1.is_active)

    def test_invalid_token(self):
        token2 = activation_token_generator.make_token(self.user2)

        response = self.client.get(
            reverse("account-activate", args=[self.user1_encoded_id, token2])
        )
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "users/account_activation.html")
        self.assertFalse(response.context["is_activation_successful"])
        self.assertEqual(
            response.context["error_message"],
            "The activation link is invalid or has expired",
        )
        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertFalse(self.user1.is_active)
        self.assertFalse(self.user1.is_active)
