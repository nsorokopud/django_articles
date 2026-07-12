from unittest.mock import patch

from django.contrib.staticfiles.storage import ContentFile
from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import TestCase, override_settings

from users.models import DEFAULT_PROFILE_IMAGE, Profile, User
from users.services.profiles import create_user_profile, update_user_profile
from users.signals import create_profile


class TestCreateUserProfile(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def tearDown(self):
        signals.post_save.connect(create_profile, sender=User)

    def test_creates_profile(self):
        signals.post_save.disconnect(create_profile, sender=User)

        u = User.objects.create(username="user", email="test1@test.com")

        with self.assertRaises(Profile.DoesNotExist):
            profile = Profile.objects.get(user=u)

        profile = create_user_profile(u)
        self.assertEqual(profile.user, u)
        self.assertEqual(Profile.objects.filter(user=u).first(), profile)


@override_settings(MEDIA_ROOT="/tmp/test-media")
class TestUpdateUserProfile(TestCase):
    def test_updates_username(self):
        user = User.objects.create_user(
            username="old_username", email="user@test.com", password="testpass123"
        )

        updated_user, profile = update_user_profile(
            user=user,
            username="new_username",
            image=None,
            image_changed=False,
            notification_emails_allowed=user.profile.notification_emails_allowed,
        )

        user.refresh_from_db()
        profile.refresh_from_db()

        self.assertEqual(updated_user.pk, user.pk)
        self.assertEqual(user.username, "new_username")
        self.assertEqual(profile.user, user)

    def test_updates_notification_emails_allowed(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        _, profile = update_user_profile(
            user=user,
            username=user.username,
            image=None,
            image_changed=False,
            notification_emails_allowed=False,
        )

        profile.refresh_from_db()

        self.assertFalse(profile.notification_emails_allowed)

    def test_updates_profile_image_when_image_changed(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        image = ContentFile(b"fake image content", name="avatar.jpg")

        _, profile = update_user_profile(
            user=user,
            username=user.username,
            image=image,
            image_changed=True,
            notification_emails_allowed=user.profile.notification_emails_allowed,
        )

        profile.refresh_from_db()

        self.assertNotEqual(profile.image.name, DEFAULT_PROFILE_IMAGE)
        self.assertTrue(
            profile.image.name.startswith(f"users/profile_images/{user.id}/")
        )
        self.assertTrue(profile.image.name.endswith(".jpg"))

    def test_rejects_existing_username_case_insensitively(self):
        User.objects.create_user(username="Taken", email="taken@test.com")
        user = User.objects.create_user(username="user", email="user@test.com")

        with self.assertRaises(ValidationError) as context:
            update_user_profile(
                user=user,
                username="taken",
                image=None,
                image_changed=False,
                notification_emails_allowed=user.profile.notification_emails_allowed,
            )

        self.assertEqual(
            context.exception.message_dict,
            {"username": ["A user with that username already exists."]},
        )

    def test_rejects_blank_username(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            update_user_profile(
                user=user,
                username="   ",
                image=None,
                image_changed=False,
                notification_emails_allowed=user.profile.notification_emails_allowed,
            )

        self.assertEqual(
            context.exception.message_dict, {"username": ["Username is required."]}
        )

    def test_does_not_update_profile_image_when_image_not_changed(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        old_image_name = user.profile.image.name

        image = ContentFile(b"fake image content", name="avatar.jpg")

        _, profile = update_user_profile(
            user=user,
            username=user.username,
            image=image,
            image_changed=False,
            notification_emails_allowed=user.profile.notification_emails_allowed,
        )

        profile.refresh_from_db()

        self.assertEqual(profile.image.name, old_image_name)

    def test_clears_profile_image_to_default_when_image_changed_and_image_is_none(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile
        profile.image.save(
            "old_avatar.jpg", ContentFile(b"old fake image content"), save=True
        )

        self.assertNotEqual(profile.image.name, DEFAULT_PROFILE_IMAGE)

        update_user_profile(
            user=user,
            username=user.username,
            image=None,
            image_changed=True,
            notification_emails_allowed=profile.notification_emails_allowed,
        )

        profile.refresh_from_db()

        self.assertEqual(profile.image.name, DEFAULT_PROFILE_IMAGE)

    def test_replaces_profile_image_when_image_changed(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile
        profile.image.save(
            "old_avatar.jpg", ContentFile(b"old fake image content"), save=True
        )
        old_image_name = profile.image.name

        new_image = ContentFile(b"new fake image content", name="new_avatar.jpg")

        update_user_profile(
            user=user,
            username=user.username,
            image=new_image,
            image_changed=True,
            notification_emails_allowed=profile.notification_emails_allowed,
        )

        profile.refresh_from_db()

        self.assertNotEqual(profile.image.name, old_image_name)
        self.assertTrue(profile.image.name.endswith(".jpg"))

    def test_does_not_delete_image_when_image_did_not_change(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile
        profile.image.save(
            "old_avatar.jpg", ContentFile(b"old fake image content"), save=True
        )
        old_image_name = profile.image.name

        update_user_profile(
            user=user,
            username=user.username,
            image=None,
            image_changed=False,
            notification_emails_allowed=profile.notification_emails_allowed,
        )

        profile.refresh_from_db()

        self.assertEqual(profile.image.name, old_image_name)

    def test_does_not_save_when_nothing_changed(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile

        with (
            patch("users.models.User.save") as mock_user_save,
            patch("users.models.Profile.save") as mock_profile_save,
        ):
            update_user_profile(
                user=user,
                username=user.username,
                image=None,
                image_changed=False,
                notification_emails_allowed=profile.notification_emails_allowed,
            )

        mock_user_save.assert_not_called()
        mock_profile_save.assert_not_called()
