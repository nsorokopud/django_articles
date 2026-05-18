from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import TestCase

from users.models import PendingEmailChange, Profile, User
from users.services.users import (
    activate_user,
    advance_latest_article_publish_sequence,
    create_user_profile,
    register_user,
)
from users.signals import create_profile


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


class TestUserServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def tearDown(self):
        signals.post_save.connect(create_profile, sender=User)

    def test_create_user_profile(self):
        signals.post_save.disconnect(create_profile, sender=User)

        u = User.objects.create(username="user", email="test1@test.com")

        with self.assertRaises(Profile.DoesNotExist):
            profile = Profile.objects.get(user=u)

        profile = create_user_profile(u)
        self.assertEqual(profile.user, u)
        self.assertEqual(Profile.objects.filter(user=u).first(), profile)


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
