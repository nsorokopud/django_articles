from django.db import IntegrityError, transaction
from django.test import TestCase

from users.models import User


class TestUserModel(TestCase):
    def test_email_is_lowercased_on_create(self):
        user = User.objects.create_user(
            username="user", email="User.Test@Test.COM", password="testpass123"
        )
        user.refresh_from_db()

        self.assertEqual(user.email, "user.test@test.com")

    def test_email_is_lowercased_on_save(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        user.email = "New.Email@Test.COM"
        user.save(update_fields=["email"])
        user.refresh_from_db()

        self.assertEqual(user.email, "new.email@test.com")

    def test_email_case_insensitive_unique_constraint(self):
        User.objects.create_user(
            username="user1", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="user2", email="USER@test.com", password="testpass123"
                )

    def test_email_cannot_be_blank(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="user", email="", password="testpass123"
                )
