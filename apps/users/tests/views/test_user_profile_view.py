from io import BytesIO
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from users.models import DEFAULT_PROFILE_IMAGE, User


class TestUserProfileView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("user-profile")
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def _make_uploaded_image(self, filename: str = "test_image.jpg"):
        image = Image.new("RGB", (1, 1), color="white")
        image_file = BytesIO()
        image.save(image_file, format="JPEG")
        image_file.seek(0)

        return SimpleUploadedFile(
            filename, image_file.read(), content_type="image/jpeg"
        )

    def test_get(self):
        response = self.client.get(self.url)
        redirect_url = f'{reverse("login")}?next={self.url}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")

    def test_post_anonymous(self):
        response = self.client.post(self.url, {"username": "abcd"})
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

    def test_post_logged_in(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, {"username": "abcd", "notification_emails_allowed": True}
        )

        self.assertRedirects(
            response, self.url, status_code=302, target_status_code=200
        )

        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.username, "abcd")
        self.assertTrue(self.user.profile.notification_emails_allowed)
        self.assertEqual(self.user.profile.image.name, DEFAULT_PROFILE_IMAGE)

    def test_post_invalid_user_form_data(self):
        self.assertTrue(self.user.profile.notification_emails_allowed)

        invalid_data = {"username": "", "notification_emails_allowed": False}

        self.client.force_login(self.user)
        response = self.client.post(self.url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertIn("user_form", response.context)
        self.assertFalse(response.context["user_form"].is_valid())
        self.assertEqual(
            response.context["user_form"].errors["username"][0],
            "This field is required.",
        )

        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.username, "user")
        self.assertTrue(self.user.profile.notification_emails_allowed)
        self.assertEqual(self.user.profile.image.name, DEFAULT_PROFILE_IMAGE)

    def test_post_without_profile_image(self):
        data = {"username": "user", "notification_emails_allowed": True}

        self.assertEqual(self.user.profile.image.name, DEFAULT_PROFILE_IMAGE)

        self.client.force_login(self.user)
        response = self.client.post(self.url, data)

        self.assertRedirects(
            response, self.url, status_code=302, target_status_code=200
        )

        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.profile.image.name, DEFAULT_PROFILE_IMAGE)

    @patch("users.models.uuid4")
    def test_post_valid_data_does_not_delete_default_profile_image(self, mock_uuid):
        mock_uuid.return_value.hex = "abc123"
        uploaded_image = self._make_uploaded_image("test_image.jpg")

        data = {
            "username": "newusername",
            "notification_emails_allowed": False,
            "image": uploaded_image,
        }

        self.assertEqual(self.user.username, "user")
        self.assertEqual(self.user.profile.image.name, DEFAULT_PROFILE_IMAGE)
        self.assertTrue(self.user.profile.notification_emails_allowed)

        self.client.force_login(self.user)

        response = self.client.post(self.url, data)

        self.assertRedirects(
            response, self.url, status_code=302, target_status_code=200
        )

        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.username, "newusername")
        self.assertFalse(self.user.profile.notification_emails_allowed)
        self.assertTrue(
            self.user.profile.image.name.startswith(
                f"users/profile_images/{self.user.id}/abc123"
            )
        )
        self.assertTrue(self.user.profile.image.name.endswith(".jpg"))

    @patch("users.models.uuid4")
    def test_post_replaces_old_profile_image(self, mock_uuid):
        mock_uuid.return_value.hex = "abc123"
        self.client.force_login(self.user)

        profile = self.user.profile
        profile.image.save(
            "old_avatar.jpg", ContentFile(b"old fake image content"), save=True
        )

        uploaded_image = self._make_uploaded_image("test_image.jpg")

        data = {
            "username": "newusername",
            "notification_emails_allowed": False,
            "image": uploaded_image,
        }

        response = self.client.post(self.url, data)

        self.assertRedirects(
            response, self.url, status_code=302, target_status_code=200
        )

        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.username, "newusername")
        self.assertFalse(self.user.profile.notification_emails_allowed)
        self.assertTrue(
            self.user.profile.image.name.startswith(
                f"users/profile_images/{self.user.id}/abc123"
            )
        )
        self.assertTrue(self.user.profile.image.name.endswith(".jpg"))

    def test_post_invalid_profile_image(self):
        uploaded_file = SimpleUploadedFile(
            "not_image.txt", b"not an image", content_type="text/plain"
        )

        data = {
            "username": "user",
            "notification_emails_allowed": True,
            "image": uploaded_file,
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertIn("profile_form", response.context)
        self.assertFalse(response.context["profile_form"].is_valid())
        self.assertIn("image", response.context["profile_form"].errors)

        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.username, "user")
        self.assertTrue(self.user.profile.notification_emails_allowed)
        self.assertEqual(self.user.profile.image.name, DEFAULT_PROFILE_IMAGE)
