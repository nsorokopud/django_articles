from django.test import TestCase
from django.utils import timezone

from notifications.models import Notification, NotificationType
from notifications.services.actions import (
    delete_notification,
    mark_notification_as_read,
)
from users.models import User


class TestActionServices(TestCase):
    def setUp(self) -> None:
        self.user1 = User.objects.create_user(
            username="u1",
            email="u1@test.com",
        )

        self.user2 = User.objects.create_user(
            username="u2",
            email="u2@test.com",
        )

        self.notification = Notification.objects.create(
            recipient=self.user1,
            notification_type=NotificationType.SYSTEM,
            title="T",
            body="B",
        )

        self.user1.unread_notifications_count = 1
        self.user1.save(update_fields=["unread_notifications_count"])

    def test_mark_notification_as_read_success(self) -> None:
        result = mark_notification_as_read(self.notification.id, self.user1.id)

        self.assertTrue(result)

        n = Notification.objects.get(id=self.notification.id)
        self.assertIsNotNone(n.read_at)

        self.user1.refresh_from_db()
        self.assertEqual(self.user1.unread_notifications_count, 0)

    def test_mark_notification_as_read_already_read(self) -> None:
        self.notification.read_at = timezone.now()
        self.notification.save(update_fields=["read_at"])

        result = mark_notification_as_read(self.notification.id, self.user1.id)

        self.assertFalse(result)

        self.user1.refresh_from_db()
        self.assertEqual(self.user1.unread_notifications_count, 1)

    def test_mark_notification_as_read_wrong_user(self) -> None:
        result = mark_notification_as_read(self.notification.id, self.user2.id)

        self.assertFalse(result)

        self.notification.refresh_from_db()
        self.assertIsNone(self.notification.read_at)

    def test_mark_notification_as_read_missing_notification_returns_false(self) -> None:
        missing_id = self.notification.id + 99999
        result = mark_notification_as_read(missing_id, self.user1.id)
        self.assertFalse(result)

        self.user1.refresh_from_db()
        self.assertEqual(self.user1.unread_notifications_count, 1)

    def test_delete_unread_notification(self) -> None:
        result = delete_notification(self.notification.id, self.user1.id)

        self.assertTrue(result)

        self.assertFalse(Notification.objects.filter(id=self.notification.id).exists())

        self.user1.refresh_from_db()
        self.assertEqual(self.user1.unread_notifications_count, 0)

    def test_delete_unread_does_not_decrement_below_zero(self) -> None:
        self.user1.unread_notifications_count = 0
        self.user1.save(update_fields=["unread_notifications_count"])

        result = delete_notification(self.notification.id, self.user1.id)
        self.assertTrue(result)

        self.user1.refresh_from_db()
        self.assertEqual(self.user1.unread_notifications_count, 0)

    def test_delete_read_notification_does_not_change_counter(self) -> None:
        self.notification.read_at = timezone.now()
        self.notification.save(update_fields=["read_at"])

        result = delete_notification(self.notification.id, self.user1.id)

        self.assertTrue(result)

        self.user1.refresh_from_db()
        self.assertEqual(self.user1.unread_notifications_count, 1)

    def test_delete_notification_wrong_user(self) -> None:
        result = delete_notification(self.notification.id, self.user2.id)

        self.assertFalse(result)

        self.assertTrue(Notification.objects.filter(id=self.notification.id).exists())
