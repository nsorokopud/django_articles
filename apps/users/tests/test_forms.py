from django.test import TestCase

from ..forms import UserUpdateForm
from ..models import User


class TestUserUpdateForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_valid_form(self):
        form = UserUpdateForm(
            data={"username": "newusername"},
            instance=self.user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newusername")

    def test_invalid_username(self):
        User.objects.create_user(username="existinguser", email="existinguser@test.com")
        form = UserUpdateForm(
            data={"username": "existinguser"},
            instance=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertEqual(
            form.errors["username"][0], "A user with that username already exists."
        )

    def test_same_username(self):
        form = UserUpdateForm(
            data={"username": "user"},
            instance=self.user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "user")

    def test_email_is_not_changed(self):
        form = UserUpdateForm(
            data={"username": "newusername", "email": "newemail@test.com"},
            instance=self.user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newusername")
        self.assertEqual(self.user.email, "user@test.com")
