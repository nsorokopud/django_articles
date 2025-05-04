from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.test import TestCase

from users.forms import (
    EmailAddressModelForm,
    UserUpdateForm,
)
from users.models import User


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


class TestEmailAddressModelForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="u@t.com")
        self.user2 = User.objects.create_user(username="user2", email="u2@t.com")
        self.email = EmailAddress.objects.create(
            user=self.user, email="u@t.com", verified=True, primary=True
        )
        self.form = EmailAddressModelForm(
            {
                "user": self.user2,
                "email": "u2@t.com",
                "verified": False,
                "primary": False,
            },
            instance=self.email,
        )

    def test_clean_no_user(self):
        form = EmailAddressModelForm(
            {
                "email": "u@test.com",
                "verified": False,
                "primary": False,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {"user": ["This field is required."], "__all__": ["User is required."]},
        )

    def test_clean_enforce_unique_email_type_per_user_called(self):
        with patch("users.forms.enforce_unique_email_type_per_user") as mock:
            self.assertTrue(self.form.is_valid())

        mock.assert_called_once()
        args, _ = mock.call_args
        instance = args[0]

        self.assertEqual(instance.pk, self.email.pk)
        self.assertEqual(instance.user, self.user2)
        self.assertEqual(instance.email, "u2@t.com")
        self.assertEqual(instance.verified, False)
        self.assertEqual(instance.primary, False)

    def test_modify_instance(self):
        self.assertTrue(self.form.is_valid())
        self.form.save()

        self.email.refresh_from_db()
        self.assertEqual(self.email.user, self.user2)
        self.assertEqual(self.email.email, "u2@t.com")
        self.assertEqual(self.email.verified, False)
        self.assertEqual(self.email.primary, False)
