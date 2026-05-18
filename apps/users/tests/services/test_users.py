from django.db.models import signals
from django.test import TestCase

from users.models import Profile, User
from users.services.users import (
    activate_user,
    advance_latest_article_publish_sequence,
    create_user_profile,
    deactivate_user,
)
from users.signals import create_profile


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

    def test_deactivate_user(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        self.assertTrue(user.is_active)
        deactivate_user(user)
        self.assertFalse(user.is_active)

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
