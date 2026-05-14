from django.db import IntegrityError, transaction
from django.test import TestCase

from users.models import DEFAULT_PROFILE_IMAGE, Profile, User, profile_image_upload_path


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


class TestProfileModel(TestCase):
    def test_profile_uses_default_image(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        self.assertEqual(profile.image.name, DEFAULT_PROFILE_IMAGE)

    def test_profile_image_upload_path_uses_user_id(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "My Avatar.JPG")

        self.assertTrue(path.startswith(f"users/profile_images/{user.id}/My_Avatar_"))
        self.assertTrue(path.endswith(".jpg"))

    def test_profile_image_upload_path_sanitizes_filename(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "../../...///bad file name.PNG")

        self.assertTrue(
            path.startswith(f"users/profile_images/{user.id}/bad_file_name_")
        )
        self.assertTrue(path.endswith(".png"))
        self.assertNotIn("..", path)

    def test_profile_image_upload_path_uses_avatar_when_base_name_is_empty(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "...")

        self.assertTrue(path.startswith(f"users/profile_images/{user.id}/avatar_"))

    def test_profile_image_upload_path_requires_user_id(self):
        profile = Profile()

        with self.assertRaisesMessage(
            ValueError, "user_id is required to upload profile images"
        ):
            profile_image_upload_path(profile, "avatar.jpg")
