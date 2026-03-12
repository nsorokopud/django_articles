from django.test import TestCase
from django.utils import timezone

from notifications.models import Notification, NotificationType
from notifications.services.counters import (
    _apply_unread_count_updates,
    _get_actual_unread_counts,
    _load_user_batch,
    _plan_unread_count_updates,
    sync_unread_notification_counts,
)
from users.models import User


def _create_notification(
    *,
    recipient: User,
    read: bool = False,
    title: str = "T",
    body: str = "B",
) -> Notification:
    return Notification.objects.create(
        recipient=recipient,
        notification_type=NotificationType.SYSTEM,
        level=Notification.Level.INFO,
        title=title,
        body=body,
        payload={},
        dedupe_key="",
        read_at=timezone.now() if read else None,
    )


class TestSyncUnreadNotificationCounts(TestCase):
    def setUp(self) -> None:
        self.u1 = User.objects.create_user(
            username="u1",
            email="u1@test.com",
            unread_notifications_count=0,
        )
        self.u2 = User.objects.create_user(
            username="u2",
            email="u2@test.com",
            unread_notifications_count=99,
        )
        self.u3 = User.objects.create_user(
            username="u3",
            email="u3@test.com",
            unread_notifications_count=1,
        )
        self.u4 = User.objects.create_user(
            username="u4",
            email="u4@test.com",
            unread_notifications_count=5,
        )

    def test_raises_value_error_for_non_positive_batch_size(self) -> None:
        with self.assertRaises(ValueError):
            sync_unread_notification_counts(batch_size=0)

        with self.assertRaises(ValueError):
            sync_unread_notification_counts(batch_size=-1)

    def test_syncs_drifted_counts_and_returns_stats(self) -> None:
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u1, read=False)

        _create_notification(recipient=self.u2, read=False)
        _create_notification(recipient=self.u2, read=False)
        _create_notification(recipient=self.u2, read=False)

        _create_notification(recipient=self.u3, read=True)

        stats = sync_unread_notification_counts(batch_size=2)

        self.assertEqual(
            stats,
            {
                "users_checked": 4,
                "users_updated": 4,
                "users_zeroed": 2,
            },
        )

        self.u1.refresh_from_db()
        self.u2.refresh_from_db()
        self.u3.refresh_from_db()
        self.u4.refresh_from_db()

        self.assertEqual(self.u1.unread_notifications_count, 2)
        self.assertEqual(self.u2.unread_notifications_count, 3)
        self.assertEqual(self.u3.unread_notifications_count, 0)
        self.assertEqual(self.u4.unread_notifications_count, 0)

    def test_sync_updates_only_selected_users_when_user_ids_are_provided(self) -> None:
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u2, read=False)

        original_u3_count = self.u3.unread_notifications_count
        original_u4_count = self.u4.unread_notifications_count

        stats = sync_unread_notification_counts(
            user_ids=[self.u1.id, self.u2.id],
            batch_size=10,
        )

        self.assertEqual(
            stats,
            {
                "users_checked": 2,
                "users_updated": 2,
                "users_zeroed": 0,
            },
        )

        self.u1.refresh_from_db()
        self.u2.refresh_from_db()
        self.u3.refresh_from_db()
        self.u4.refresh_from_db()

        self.assertEqual(self.u1.unread_notifications_count, 2)
        self.assertEqual(self.u2.unread_notifications_count, 1)
        self.assertEqual(self.u3.unread_notifications_count, original_u3_count)
        self.assertEqual(self.u4.unread_notifications_count, original_u4_count)

    def test_sync_with_no_drift_returns_zero_updates(self) -> None:
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u2, read=False)
        _create_notification(recipient=self.u2, read=False)
        _create_notification(recipient=self.u3, read=True)

        self.u1.unread_notifications_count = 1
        self.u2.unread_notifications_count = 2
        self.u3.unread_notifications_count = 0
        self.u4.unread_notifications_count = 0
        self.u1.save(update_fields=["unread_notifications_count"])
        self.u2.save(update_fields=["unread_notifications_count"])
        self.u3.save(update_fields=["unread_notifications_count"])
        self.u4.save(update_fields=["unread_notifications_count"])

        stats = sync_unread_notification_counts(batch_size=3)

        self.assertEqual(
            stats,
            {
                "users_checked": 4,
                "users_updated": 0,
                "users_zeroed": 0,
            },
        )

    def test_sync_ignores_read_notifications_when_counting(self) -> None:
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u1, read=True)
        _create_notification(recipient=self.u1, read=True)

        stats = sync_unread_notification_counts(batch_size=10)

        self.assertEqual(stats["users_checked"], 4)
        self.assertEqual(stats["users_updated"], 4)
        self.assertEqual(stats["users_zeroed"], 3)

        self.u1.refresh_from_db()
        self.assertEqual(self.u1.unread_notifications_count, 1)

    def test_sync_with_empty_user_ids_checks_no_users(self) -> None:
        stats = sync_unread_notification_counts(
            user_ids=[],
            batch_size=10,
        )

        self.assertEqual(
            stats,
            {
                "users_checked": 0,
                "users_updated": 0,
                "users_zeroed": 0,
            },
        )

        self.u1.refresh_from_db()
        self.u2.refresh_from_db()
        self.u3.refresh_from_db()
        self.u4.refresh_from_db()

        self.assertEqual(self.u1.unread_notifications_count, 0)
        self.assertEqual(self.u2.unread_notifications_count, 99)
        self.assertEqual(self.u3.unread_notifications_count, 1)
        self.assertEqual(self.u4.unread_notifications_count, 5)

    def test_sync_accepts_generator_for_user_ids(self) -> None:
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u2, read=False)

        user_ids_generator = (uid for uid in [self.u1.id, self.u2.id])

        stats = sync_unread_notification_counts(
            user_ids=user_ids_generator,
            batch_size=10,
        )

        self.assertEqual(
            stats,
            {
                "users_checked": 2,
                "users_updated": 2,
                "users_zeroed": 0,
            },
        )

        self.u1.refresh_from_db()
        self.u2.refresh_from_db()
        self.u3.refresh_from_db()
        self.u4.refresh_from_db()

        self.assertEqual(self.u1.unread_notifications_count, 2)
        self.assertEqual(self.u2.unread_notifications_count, 1)
        self.assertEqual(self.u3.unread_notifications_count, 1)
        self.assertEqual(self.u4.unread_notifications_count, 5)


class TestCounterHelpers(TestCase):
    def setUp(self) -> None:
        self.u1 = User.objects.create_user(
            username="u1",
            email="u1@test.com",
            unread_notifications_count=7,
        )
        self.u2 = User.objects.create_user(
            username="u2",
            email="u2@test.com",
            unread_notifications_count=0,
        )
        self.u3 = User.objects.create_user(
            username="u3",
            email="u3@test.com",
            unread_notifications_count=2,
        )

    def test_load_user_batch_returns_ordered_slice_after_last_id(self) -> None:
        batch = _load_user_batch(
            base_users=User.objects.all().order_by("id"),
            last_id=0,
            batch_size=2,
        )

        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0]["id"], self.u1.id)
        self.assertEqual(batch[1]["id"], self.u2.id)

        next_batch = _load_user_batch(
            base_users=User.objects.all().order_by("id"),
            last_id=self.u2.id,
            batch_size=2,
        )

        self.assertEqual(len(next_batch), 1)
        self.assertEqual(next_batch[0]["id"], self.u3.id)

    def test_get_actual_unread_counts_counts_only_unread(self) -> None:
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u1, read=False)
        _create_notification(recipient=self.u1, read=True)
        _create_notification(recipient=self.u2, read=True)
        _create_notification(recipient=self.u3, read=False)

        counts = _get_actual_unread_counts([self.u1.id, self.u2.id, self.u3.id])

        self.assertEqual(
            counts,
            {
                self.u1.id: 2,
                self.u3.id: 1,
            },
        )

    def test_plan_unread_count_updates_splits_zero_and_nonzero_updates(self) -> None:
        user_batch = [
            {"id": self.u1.id, "unread_notifications_count": 7},
            {"id": self.u2.id, "unread_notifications_count": 0},
            {"id": self.u3.id, "unread_notifications_count": 2},
        ]
        actual_unread_counts = {
            self.u1.id: 0,
            self.u2.id: 0,
            self.u3.id: 5,
        }

        ids_to_zero, ids_to_fix_by_count = _plan_unread_count_updates(
            user_batch=user_batch,
            actual_unread_counts=actual_unread_counts,
        )

        self.assertEqual(ids_to_zero, [self.u1.id])
        self.assertEqual(ids_to_fix_by_count, {5: [self.u3.id]})

    def test_apply_unread_count_updates_updates_rows_and_returns_stats(self) -> None:
        updated, zeroed = _apply_unread_count_updates(
            ids_to_zero=[self.u1.id],
            ids_to_fix_by_count={5: [self.u3.id]},
        )

        self.assertEqual(updated, 2)
        self.assertEqual(zeroed, 1)

        self.u1.refresh_from_db()
        self.u2.refresh_from_db()
        self.u3.refresh_from_db()

        self.assertEqual(self.u1.unread_notifications_count, 0)
        self.assertEqual(self.u2.unread_notifications_count, 0)
        self.assertEqual(self.u3.unread_notifications_count, 5)

    def test_apply_unread_count_updates_skips_noop_updates(self) -> None:
        self.u1.unread_notifications_count = 0
        self.u1.save(update_fields=["unread_notifications_count"])
        self.u3.unread_notifications_count = 5
        self.u3.save(update_fields=["unread_notifications_count"])

        updated, zeroed = _apply_unread_count_updates(
            ids_to_zero=[self.u1.id],
            ids_to_fix_by_count={5: [self.u3.id]},
        )

        self.assertEqual(updated, 0)
        self.assertEqual(zeroed, 0)

    def test_plan_unread_count_updates_groups_changed_counts(
        self,
    ) -> None:
        user_batch = [
            {"id": 1, "unread_notifications_count": 0},
            {"id": 2, "unread_notifications_count": 3},
        ]
        actual_unread_counts = {
            1: 0,
            2: 1,
        }

        ids_to_zero, ids_to_fix_by_count = _plan_unread_count_updates(
            user_batch=user_batch,
            actual_unread_counts=actual_unread_counts,
        )

        self.assertEqual(ids_to_zero, [])
        self.assertEqual(ids_to_fix_by_count, {1: [2]})
