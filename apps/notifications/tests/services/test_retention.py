from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from notifications.models import Notification
from notifications.services.retention import (
    _delete_old_read_notifications_batch,
    cleanup_old_read_notifications,
)
from users.models import User


def _create_notification(user: User, *, read_at=None, created_at=None) -> Notification:
    n = Notification.objects.create(
        recipient=user,
        title="t",
        body="b",
    )

    updates = {}

    if read_at is not None:
        updates["read_at"] = read_at

    if created_at is not None:
        updates["created_at"] = created_at

    if updates:
        Notification.objects.filter(pk=n.pk).update(**updates)
        n.refresh_from_db()

    return n


class TestCleanupOldReadNotifications(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="u1",
            email="u1@test.com",
        )

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=3,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_uses_settings_defaults(self):
        now = timezone.now()
        old_read_1 = _create_notification(self.user, read_at=now - timedelta(days=40))
        old_read_2 = _create_notification(self.user, read_at=now - timedelta(days=35))
        recent_read = _create_notification(self.user, read_at=now - timedelta(days=5))
        unread_old = _create_notification(self.user, read_at=None)

        deleted = cleanup_old_read_notifications()

        self.assertEqual(deleted, 2)
        self.assertFalse(Notification.objects.filter(pk=old_read_1.pk).exists())
        self.assertFalse(Notification.objects.filter(pk=old_read_2.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=recent_read.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=unread_old.pk).exists())

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=5,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_deletes_only_old_read_notifications(self):
        now = timezone.now()
        old_read_1 = _create_notification(self.user, read_at=now - timedelta(days=100))
        old_read_2 = _create_notification(self.user, read_at=now - timedelta(days=31))
        recent_read = _create_notification(self.user, read_at=now - timedelta(days=29))
        unread = _create_notification(self.user, read_at=None)

        deleted = cleanup_old_read_notifications()

        self.assertEqual(deleted, 2)
        self.assertFalse(Notification.objects.filter(pk=old_read_1.pk).exists())
        self.assertFalse(Notification.objects.filter(pk=old_read_2.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=recent_read.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=unread.pk).exists())

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=1,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_respects_max_batches(self):
        now = timezone.now()
        _create_notification(self.user, read_at=now - timedelta(days=60))
        _create_notification(self.user, read_at=now - timedelta(days=61))
        _create_notification(self.user, read_at=now - timedelta(days=62))

        deleted = cleanup_old_read_notifications()

        self.assertEqual(deleted, 2)
        self.assertEqual(Notification.objects.count(), 1)

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=10,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_stops_when_no_more_rows(self):
        now = timezone.now()
        _create_notification(self.user, read_at=now - timedelta(days=60))
        _create_notification(self.user, read_at=now - timedelta(days=61))
        _create_notification(self.user, read_at=now - timedelta(days=62))

        deleted = cleanup_old_read_notifications()

        self.assertEqual(deleted, 3)
        self.assertEqual(Notification.objects.count(), 0)

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=0,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_returns_zero_when_max_batches_is_zero(self):
        now = timezone.now()
        n = _create_notification(self.user, read_at=now - timedelta(days=60))

        deleted = cleanup_old_read_notifications()

        self.assertEqual(deleted, 0)
        self.assertTrue(Notification.objects.filter(pk=n.pk).exists())

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=1,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_raises_for_invalid_older_than_days(self):
        with self.assertRaisesMessage(ValueError, "older_than_days must be > 0"):
            cleanup_old_read_notifications(older_than_days=0)

        with self.assertRaisesMessage(ValueError, "older_than_days must be > 0"):
            cleanup_old_read_notifications(older_than_days=-1)

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=1,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_raises_for_invalid_max_batches(self):
        with self.assertRaisesMessage(ValueError, "max_batches must be >= 0"):
            cleanup_old_read_notifications(max_batches=-1)

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=None,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_raises_when_setting_resolves_max_batches_to_none(
        self,
    ):
        with self.assertRaisesMessage(ValueError, "max_batches must not be None"):
            cleanup_old_read_notifications()


class TestDeleteOldReadNotificationsBatch(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="u1",
            email="u1@test.com",
        )

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=3,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_deletes_oldest_read_rows_first(self):
        now = timezone.now()
        oldest = _create_notification(self.user, read_at=now - timedelta(days=100))
        middle = _create_notification(self.user, read_at=now - timedelta(days=90))
        newest_old = _create_notification(self.user, read_at=now - timedelta(days=80))
        recent = _create_notification(self.user, read_at=now - timedelta(days=5))
        unread = _create_notification(self.user, read_at=None)

        cutoff = now - timedelta(days=30)
        deleted = _delete_old_read_notifications_batch(cutoff=cutoff, batch_size=2)

        self.assertEqual(deleted, 2)
        self.assertFalse(Notification.objects.filter(pk=oldest.pk).exists())
        self.assertFalse(Notification.objects.filter(pk=middle.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=newest_old.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=recent.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=unread.pk).exists())

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=3,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_uses_setting_batch_size_when_omitted(
        self,
    ):
        now = timezone.now()
        _create_notification(self.user, read_at=now - timedelta(days=100))
        _create_notification(self.user, read_at=now - timedelta(days=90))
        _create_notification(self.user, read_at=now - timedelta(days=80))

        cutoff = now - timedelta(days=30)
        deleted = _delete_old_read_notifications_batch(cutoff=cutoff)

        self.assertEqual(deleted, 2)
        self.assertEqual(Notification.objects.count(), 1)

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=3,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_returns_zero_when_no_matching_rows(
        self,
    ):
        now = timezone.now()
        _create_notification(self.user, read_at=now - timedelta(days=5))
        _create_notification(self.user, read_at=None)

        cutoff = now - timedelta(days=30)
        deleted = _delete_old_read_notifications_batch(cutoff=cutoff, batch_size=10)

        self.assertEqual(deleted, 0)
        self.assertEqual(Notification.objects.count(), 2)

    @override_settings(
        NOTIFICATION_READ_RETENTION_DAYS=30,
        NOTIFICATION_CLEANUP_MAX_BATCHES=3,
        NOTIFICATION_CLEANUP_BATCH_SIZE=2,
    )
    def test_raises_for_invalid_batch_size(self):
        cutoff = timezone.now() - timedelta(days=30)

        with self.assertRaisesMessage(ValueError, "batch_size must be > 0"):
            _delete_old_read_notifications_batch(cutoff=cutoff, batch_size=0)

        with self.assertRaisesMessage(ValueError, "batch_size must be > 0"):
            _delete_old_read_notifications_batch(cutoff=cutoff, batch_size=-1)
