from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from users.models import User


class TestUserProfileView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("user-profile")
        self.user = User.objects.create_user(username="user", email="user@test.com")

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
        response = self.client.post(self.url, {"username": "abcd"})
        self.assertRedirects(
            response, self.url, status_code=302, target_status_code=200
        )

    def test_post_invalid_user_form_data(self):
        self.assertTrue(self.user.profile.notification_emails_allowed)
        invalid_data = {
            "username": "",
            "notification_emails_allowed": False,
        }

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
        self.assertEqual(self.user.username, "user")
        self.assertTrue(self.user.profile.notification_emails_allowed)

    def test_post_without_profile_image(self):
        data = {
            "username": "user",
            "notification_emails_allowed": True,
        }

        self.assertEqual(
            self.user.profile.image.name, "users/profile_images/default_avatar.jpg"
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            self.url,
            status_code=302,
            target_status_code=200,
        )

        self.assertEqual(
            self.user.profile.image.name, "users/profile_images/default_avatar.jpg"
        )

    def test_post_valid_data(self):
        image = Image.new("RGB", (1, 1), color="white")
        image_file = BytesIO()
        image.save(image_file, format="JPEG")
        image_file.seek(0)
        uploaded_image = SimpleUploadedFile(
            "test_image.jpg", image_file.read(), content_type="image/jpeg"
        )
        data = {
            "username": "newusername",
            "notification_emails_allowed": False,
            "image": uploaded_image,
        }

        self.assertEqual(self.user.username, "user")
        self.assertEqual(
            self.user.profile.image.name, "users/profile_images/default_avatar.jpg"
        )
        self.assertTrue(self.user.profile.notification_emails_allowed)

        self.client.force_login(self.user)
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            self.url,
            status_code=302,
            target_status_code=200,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newusername")
        self.assertFalse(self.user.profile.notification_emails_allowed)
        self.assertEqual(
            self.user.profile.image.name,
            "users/profile_images/test_image.jpg",
        )
