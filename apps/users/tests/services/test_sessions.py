from django.test import TestCase

from users.models import User
from users.services.sessions import invalidate_user_sessions


class TestInvalidateUserSessions(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test_user", email="test@test.com", password="testpass123"
        )

    def test_increments_session_auth_version(self):
        self.assertEqual(self.user.session_auth_version, 0)

        invalidate_user_sessions(user_id=self.user.id)

        self.user.refresh_from_db()
        self.assertEqual(self.user.session_auth_version, 1)

    def test_increments_existing_session_auth_version(self):
        User.objects.filter(pk=self.user.pk).update(session_auth_version=7)

        invalidate_user_sessions(user_id=self.user.id)

        self.user.refresh_from_db()
        self.assertEqual(self.user.session_auth_version, 8)

    def test_repeated_calls_increment_each_time(self):
        invalidate_user_sessions(user_id=self.user.id)
        invalidate_user_sessions(user_id=self.user.id)
        invalidate_user_sessions(user_id=self.user.id)

        self.user.refresh_from_db()
        self.assertEqual(self.user.session_auth_version, 3)

    def test_does_nothing_for_missing_user_id(self):
        invalidate_user_sessions(user_id=999999)

        self.user.refresh_from_db()
        self.assertEqual(self.user.session_auth_version, 0)

    def test_session_auth_hash_changes_after_invalidation(self):
        original_hash = self.user.get_session_auth_hash()

        invalidate_user_sessions(user_id=self.user.id)

        self.user.refresh_from_db()
        self.assertNotEqual(original_hash, self.user.get_session_auth_hash())
