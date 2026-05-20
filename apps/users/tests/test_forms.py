from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from users.forms import (
    EmailChangeConfirmationForm,
    EmailChangeForm,
    ProfileUpdateForm,
    UserCreationForm,
    UserUpdateForm,
)
from users.models import PendingEmailChange, Profile, User


class TestUserCreationForm(TestCase):
    def _valid_form_data(self, **overrides):
        data = {
            "username": "newuser",
            "email": "newuser@test.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
            "hcaptcha": "dummy-token",
        }
        data.update(overrides)
        return data

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_valid_form(self, mock_hcaptcha_validate):
        form = UserCreationForm(data=self._valid_form_data())

        self.assertTrue(form.is_valid(), form.errors)

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_username_is_trimmed(self, mock_hcaptcha_validate):
        form = UserCreationForm(data=self._valid_form_data(username="  newuser  "))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["username"], "newuser")

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_rejects_email_like_username(self, mock_hcaptcha_validate):
        form = UserCreationForm(data=self._valid_form_data(username="newuser@test.com"))

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"username": ["Username cannot be an email address."]}
        )

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_email_is_lowercased(self, mock_hcaptcha_validate):
        form = UserCreationForm(data=self._valid_form_data(email="NewUser@TEST.COM"))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "newuser@test.com")

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_email_is_trimmed(self, mock_hcaptcha_validate):
        form = UserCreationForm(
            data=self._valid_form_data(email="  NewUser@TEST.COM  ")
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "newuser@test.com")

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_rejects_missing_email(self, mock_hcaptcha_validate):
        form = UserCreationForm(data=self._valid_form_data(email=""))

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertEqual(form.errors["email"], ["This field is required."])

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_rejects_invalid_email(self, mock_hcaptcha_validate):
        form = UserCreationForm(data=self._valid_form_data(email="not-an-email"))

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    @patch("hcaptcha_field.fields.hCaptchaField.validate")
    def test_rejects_password_mismatch(self, mock_hcaptcha_validate):
        form = UserCreationForm(
            data=self._valid_form_data(
                password1="StrongPass123!", password2="DifferentPass123!"
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)


class TestUserUpdateForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_valid_form(self):
        form = UserUpdateForm(data={"username": "newusername"}, instance=self.user)

        self.assertTrue(form.is_valid(), form.errors)

    def test_username_is_trimmed(self):
        form = UserUpdateForm(data={"username": "  newusername  "}, instance=self.user)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["username"], "newusername")

    def test_rejects_email_like_username(self):
        form = UserUpdateForm(data={"username": "user@test.com"}, instance=self.user)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"username": ["Username cannot be an email address."]}
        )

    def test_same_username(self):
        form = UserUpdateForm(data={"username": "user"}, instance=self.user)

        self.assertTrue(form.is_valid(), form.errors)

    def test_same_username_different_case_is_allowed(self):
        form = UserUpdateForm(data={"username": "USER"}, instance=self.user)

        self.assertTrue(form.is_valid(), form.errors)

    def test_same_username_with_whitespace(self):
        form = UserUpdateForm(data={"username": "  user  "}, instance=self.user)

        self.assertTrue(form.is_valid(), form.errors)

    def test_same_username_different_case_with_whitespace_is_allowed(self):
        form = UserUpdateForm(data={"username": "  USER  "}, instance=self.user)

        self.assertTrue(form.is_valid(), form.errors)

    def test_email_is_not_changed(self):
        form = UserUpdateForm(
            data={"username": "newusername", "email": "newemail@test.com"},
            instance=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)


class TestProfileUpdateForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        self.profile = Profile.objects.get(user=self.user)

    def test_valid_without_image_upload(self):
        form = ProfileUpdateForm(
            data={"notification_emails_allowed": True}, instance=self.profile
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_with_notification_emails_disabled(self):
        form = ProfileUpdateForm(
            data={"notification_emails_allowed": False}, instance=self.profile
        )

        self.assertTrue(form.is_valid(), form.errors)

        profile = form.save()

        self.assertFalse(profile.notification_emails_allowed)
        self.assertEqual(profile.image.name, "users/profile_images/default_avatar.jpg")

    def test_valid_with_uploaded_image(self):
        image = Image.new("RGB", (1, 1), color="white")
        image_file = BytesIO()
        image.save(image_file, format="JPEG")
        image_file.seek(0)

        uploaded_image = SimpleUploadedFile(
            "test_image.jpg", image_file.read(), content_type="image/jpeg"
        )

        form = ProfileUpdateForm(
            data={"notification_emails_allowed": True},
            files={"image": uploaded_image},
            instance=self.profile,
        )

        self.assertTrue(form.is_valid(), form.errors)

        profile = form.save()

        self.assertTrue(
            profile.image.name.startswith(
                f"users/profile_images/{self.user.id}/test_image_"
            )
        )
        self.assertTrue(profile.image.name.endswith(".jpg"))

    def test_invalid_with_non_image_file(self):
        uploaded_file = SimpleUploadedFile(
            "not_image.txt", b"not an image", content_type="text/plain"
        )

        form = ProfileUpdateForm(
            data={"notification_emails_allowed": True},
            files={"image": uploaded_file},
            instance=self.profile,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_invalid_with_corrupt_image_file(self):
        uploaded_file = SimpleUploadedFile(
            "bad_image.jpg", b"not actually a jpeg", content_type="image/jpeg"
        )

        form = ProfileUpdateForm(
            data={"notification_emails_allowed": True},
            files={"image": uploaded_file},
            instance=self.profile,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_image_field_is_not_required(self):
        form = ProfileUpdateForm(instance=self.profile)

        self.assertFalse(form.fields["image"].required)


class TestEmailChangeForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_no_new_email(self):
        form = EmailChangeForm(data={}, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"new_email": ["This field is required."]})

    def test_requires_authenticated_user(self):
        form = EmailChangeForm(data={"new_email": "new@test.com"}, user=None)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"__all__": ["You must be logged in to change email."]}
        )

    def test_valid_form(self):
        form = EmailChangeForm(data={"new_email": "new@test.com"}, user=self.user)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["new_email"], "new@test.com")

    def test_valid_form_lowercases_new_email(self):
        form = EmailChangeForm(data={"new_email": "New@TEST.COM"}, user=self.user)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["new_email"], "new@test.com")


class TestEmailChangeConfirmationForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.pending_email_change = PendingEmailChange.objects.create(
            user=self.user, email="new@test.com"
        )
        self.token = "test-token"
        self.data = {}

    def test_valid_form(self):
        form = EmailChangeConfirmationForm(
            data=self.data,
            pending_email_change_public_id=self.pending_email_change.public_id,
            token=self.token,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.pending_email_change_public_id, self.pending_email_change.public_id
        )
        self.assertEqual(form.token, self.token)

    def test_missing_pending_email_change_public_id(self):
        form = EmailChangeConfirmationForm(data=self.data, token=self.token)

        self.assertFalse(form.is_valid())
        self.assertIn("Invalid email change link.", form.non_field_errors())

    def test_missing_token(self):
        form = EmailChangeConfirmationForm(
            data=self.data,
            pending_email_change_public_id=self.pending_email_change.public_id,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Invalid email change link.", form.non_field_errors())

    def test_blank_token(self):
        form = EmailChangeConfirmationForm(
            data=self.data,
            pending_email_change_public_id=self.pending_email_change.public_id,
            token="",
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Invalid email change link.", form.non_field_errors())

    def test_missing_public_id_is_invalid(self):
        form = EmailChangeConfirmationForm(
            data=self.data, pending_email_change_public_id=None, token=self.token
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Invalid email change link.", form.non_field_errors())
