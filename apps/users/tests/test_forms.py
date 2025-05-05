from unittest.mock import patch

from allauth.account.models import EmailAddress
from django import forms
from django.test import TestCase

from users.forms import (
    EmailAddressModelForm,
    EmailChangeConfirmationForm,
    EmailChangeForm,
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


class TestEmailChangeForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_no_new_email(self):
        form = EmailChangeForm(data={}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"new_email": ["This field is required."]})

    def test_new_email_same_as_old(self):
        form = EmailChangeForm(data={"new_email": self.user.email}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"new_email": ["Enter a different email address."]}
        )

    def test_unique_email_violation(self):
        user2 = User.objects.create_user(username="user2", email="user2@test.com")
        form = EmailChangeForm(data={"new_email": user2.email}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"new_email": ["A user with that email already exists."]}
        )

    @patch("users.forms.enforce_unique_email_type_per_user")
    def test_other_unfinished_email_change(self, mock_enforce):
        mock_enforce.side_effect = forms.ValidationError(
            "Other unfinished email change"
        )

        form = EmailChangeForm(data={"new_email": "new@test.com"}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "__all__": [
                    (
                        "There is an unfinished email address change process. "
                        "Cancel it to start a new one."
                    )
                ]
            },
        )

    def test_valid_form(self):
        form = EmailChangeForm(data={"new_email": "new@test.com"}, user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["new_email"], "new@test.com")


class TestEmailChangeConfirmationForm(TestCase):
    def setUp(self):
        self.user = User(username="user")
        self.data = {"token": "test-token"}

    @patch("users.forms.get_pending_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_valid_form(self, mock_check_token, mock_get_pending_email):
        mock_get_pending_email.return_value = "pending@test.com"
        mock_check_token.return_value = True

        form = EmailChangeConfirmationForm(data=self.data, user=self.user)
        self.assertTrue(form.is_valid())

    def test_missing_user(self):
        form = EmailChangeConfirmationForm(data=self.data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "You must be logged in to change the email address.",
            form.non_field_errors(),
        )

    @patch("users.forms.get_pending_email_address")
    def test_no_pending_email(self, mock_get_pending_email):
        mock_get_pending_email.return_value = None

        form = EmailChangeConfirmationForm(data=self.data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "You don't have any pending email addresses.", form.non_field_errors()
        )

    @patch("users.forms.get_pending_email_address")
    @patch("users.forms.email_change_token_generator.check_token")
    def test_invalid_token(self, mock_check_token, mock_get_pending_email):
        mock_get_pending_email.return_value = "pending@test.com"
        mock_check_token.return_value = False

        form = EmailChangeConfirmationForm(data=self.data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("Invalid token.", form.non_field_errors())
