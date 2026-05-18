from datetime import timedelta
from unittest.mock import patch

from django.contrib.staticfiles.storage import ContentFile
from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import TestCase, override_settings
from django.utils import timezone

from users.models import DEFAULT_PROFILE_IMAGE, PendingEmailChange, Profile, User
from users.services.users import (
    activate_user,
    advance_latest_article_publish_sequence,
    create_user_profile,
    register_user,
    update_user_profile,
)
from users.signals import create_profile

from ...settings import PENDING_EMAIL_CHANGE_TTL


class TestRegisterUser(TestCase):
    def test_creates_inactive_user(self):
        user = register_user(
            username="newuser", email="NEW@TEST.COM", password="testpass123"
        )

        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.email, "new@test.com")
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password("testpass123"))

    def test_strips_username_and_email(self):
        user = register_user(
            username="  newuser  ", email="  NEW@TEST.COM  ", password="testpass123"
        )

        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.email, "new@test.com")

    def test_rejects_blank_username(self):
        with self.assertRaises(ValidationError) as context:
            register_user(username="   ", email="new@test.com", password="testpass123")

        self.assertEqual(
            context.exception.message_dict, {"username": ["Username is required."]}
        )

    def test_rejects_blank_email(self):
        with self.assertRaises(ValidationError) as context:
            register_user(username="newuser", email="   ", password="testpass123")

        self.assertEqual(
            context.exception.message_dict, {"email": ["Email is required."]}
        )

    def test_rejects_invalid_email(self):
        with self.assertRaises(ValidationError):
            register_user(
                username="newuser", email="not-an-email", password="testpass123"
            )

    def test_rejects_existing_email_case_insensitively(self):
        User.objects.create_user(
            username="existing", email="taken@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="newuser", email="TAKEN@TEST.COM", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"email": ["A user with that email already exists."]},
        )

    def test_rejects_email_used_by_pending_email_change(self):
        existing_user = User.objects.create_user(
            username="existing", email="existing@test.com", password="testpass123"
        )
        PendingEmailChange.objects.create(user=existing_user, email="pending@test.com")

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="newuser", email="PENDING@TEST.COM", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"email": ["That email address is currently pending confirmation."]},
        )

    def test_rejects_existing_username(self):
        User.objects.create_user(
            username="taken", email="taken@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="taken", email="new@test.com", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"username": ["A user with that username already exists."]},
        )

    def test_deletes_expired_pending_email_change(self):
        existing_user = User.objects.create_user(
            username="existing", email="existing@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=existing_user, email="pending@test.com"
        )
        PendingEmailChange.objects.filter(pk=pending_email_change.pk).update(
            created_at=timezone.now() - PENDING_EMAIL_CHANGE_TTL - timedelta(seconds=1)
        )

        user = register_user(
            username="newuser", email="PENDING@TEST.COM", password="testpass123"
        )

        self.assertEqual(user.email, "pending@test.com")
        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )


class TestActivateUser(TestCase):
    def test_activates_user(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

        self.assertFalse(user.is_active)

        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)

    def test_is_idempotent(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

        activate_user(user)
        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)

    def test_keeps_user_active_when_already_active(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=True
        )

        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)

    def test_does_not_modify_email(self):
        user = User.objects.create_user(
            username="user", email="User@Test.COM", is_active=False
        )

        activate_user(user)
        user.refresh_from_db()

        self.assertEqual(user.email, "user@test.com")
        self.assertTrue(user.is_active)


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
class TestUpdateUserProfileService(TestCase):
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

    def test_deletes_old_profile_image_after_commit_when_replaced(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile
        profile.image.save(
            "old_avatar.jpg", ContentFile(b"old fake image content"), save=True
        )
        old_image_name = profile.image.name

        new_image = ContentFile(b"new fake image content", name="new_avatar.jpg")

        with patch("users.services.users._delete_profile_image") as mock_delete:
            with self.captureOnCommitCallbacks(execute=True):
                update_user_profile(
                    user=user,
                    username=user.username,
                    image=new_image,
                    image_changed=True,
                    notification_emails_allowed=profile.notification_emails_allowed,
                )

        mock_delete.assert_called_once_with(old_image_name)

    def test_deletes_old_profile_image_after_commit_when_cleared(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile
        profile.image.save(
            "old_avatar.jpg", ContentFile(b"old fake image content"), save=True
        )
        old_image_name = profile.image.name

        with patch("users.services.users._delete_profile_image") as mock_delete:
            with self.captureOnCommitCallbacks(execute=True):
                update_user_profile(
                    user=user,
                    username=user.username,
                    image=None,
                    image_changed=True,
                    notification_emails_allowed=profile.notification_emails_allowed,
                )

        mock_delete.assert_called_once_with(old_image_name)

    def test_does_not_delete_default_profile_image(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile

        new_image = ContentFile(b"new fake image content", name="new_avatar.jpg")

        with patch("users.services.users._delete_profile_image") as mock_delete:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                update_user_profile(
                    user=user,
                    username=user.username,
                    image=new_image,
                    image_changed=True,
                    notification_emails_allowed=profile.notification_emails_allowed,
                )

        self.assertEqual(callbacks, [])
        mock_delete.assert_not_called()

    def test_does_not_delete_image_when_image_did_not_change(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = user.profile
        profile.image.save(
            "old_avatar.jpg", ContentFile(b"old fake image content"), save=True
        )
        old_image_name = profile.image.name

        with patch("users.services.users._delete_profile_image") as mock_delete:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                update_user_profile(
                    user=user,
                    username=user.username,
                    image=None,
                    image_changed=False,
                    notification_emails_allowed=profile.notification_emails_allowed,
                )

        profile.refresh_from_db()

        self.assertEqual(profile.image.name, old_image_name)
        self.assertEqual(callbacks, [])
        mock_delete.assert_not_called()

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


class TestAdvanceLatestArticlePublishSequence(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", latest_article_publish_sequence=10
        )

    def test_updates_sequence_when_new_value_is_greater(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id, publish_sequence=15
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 15)

    def test_does_not_update_sequence_when_new_value_is_equal(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id, publish_sequence=10
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)

    def test_does_not_update_sequence_when_new_value_is_smaller(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id, publish_sequence=5
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)

    def test_does_nothing_when_user_does_not_exist(self):
        advance_latest_article_publish_sequence(user_id=999999, publish_sequence=20)

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)
