from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from notifications.models import Notification, NotificationType
from notifications.selectors.inbox import INBOX_MAX_PAGE_SIZE, get_notifications_page
from users.models import User


class TestGetNotificationsPage(TestCase):
    def setUp(self) -> None:
        self.u1 = User.objects.create_user(username="u1", email="u1@test.com")
        self.u2 = User.objects.create_user(username="u2", email="u2@test.com")

    def _create_notification(
        self,
        *,
        user: User,
        title: str,
        is_read: bool = False,
        payload=None,
        created_at=None,
        last_event_at=None,
        notification_type=NotificationType.SYSTEM,
    ) -> Notification:
        if payload is None:
            payload = {"link": "/x/"}
        if created_at is None:
            created_at = timezone.now()
        if last_event_at is None:
            last_event_at = created_at

        n = Notification.objects.create(
            recipient=user,
            notification_type=notification_type,
            level=Notification.Level.INFO,
            title=title,
            body=f"body:{title}",
            payload=payload,
            created_at=created_at,
            last_event_at=last_event_at,
        )
        if is_read:
            n.read_at = timezone.now()
            n.save(update_fields=["read_at"])
        return n

    def _cursor_for(self, notification: Notification) -> dict:
        return {
            "last_event_at": notification.last_event_at.isoformat(),
            "id": notification.id,
        }

    def test_returns_empty_when_user_has_no_notifications(self) -> None:
        res = get_notifications_page(user_id=self.u1.id)

        self.assertEqual(res["items"], [])
        self.assertIsNone(res["next_before_cursor"])
        self.assertFalse(res["has_more"])

    def test_initial_page_orders_newest_first_and_sets_next_before_cursor(self) -> None:
        base = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=base - timedelta(minutes=3)
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=base - timedelta(minutes=2)
        )
        n3 = self._create_notification(
            user=self.u1, title="n3", last_event_at=base - timedelta(minutes=1)
        )

        res = get_notifications_page(user_id=self.u1.id, limit=2)

        self.assertEqual([x["id"] for x in res["items"]], [n3.id, n2.id])
        self.assertEqual(res["next_before_cursor"], self._cursor_for(n2))
        self.assertTrue(res["has_more"])

        item = res["items"][0]
        self.assertIn("timestamp", item)
        self.assertIn("last_event_at", item)
        self.assertIn("payload", item)
        self.assertEqual(item["is_read"], False)

        self._create_notification(user=self.u2, title="other", last_event_at=base)

        res2 = get_notifications_page(user_id=self.u1.id, limit=10)
        self.assertEqual([x["id"] for x in res2["items"]], [n3.id, n2.id, n1.id])

    def test_initial_page_uses_id_as_tie_breaker_when_last_event_at_matches(
        self,
    ) -> None:
        same_time = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=same_time
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=same_time
        )
        n3 = self._create_notification(
            user=self.u1, title="n3", last_event_at=same_time
        )

        res = get_notifications_page(user_id=self.u1.id, limit=10)

        self.assertEqual([x["id"] for x in res["items"]], [n3.id, n2.id, n1.id])

    def test_before_cursor_paginates_older_items(self) -> None:
        base = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=base - timedelta(minutes=4)
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=base - timedelta(minutes=3)
        )
        n3 = self._create_notification(
            user=self.u1, title="n3", last_event_at=base - timedelta(minutes=2)
        )
        n4 = self._create_notification(
            user=self.u1, title="n4", last_event_at=base - timedelta(minutes=1)
        )

        first = get_notifications_page(user_id=self.u1.id, limit=2)

        self.assertEqual([x["id"] for x in first["items"]], [n4.id, n3.id])
        self.assertEqual(first["next_before_cursor"], self._cursor_for(n3))
        self.assertTrue(first["has_more"])

        cursor = first["next_before_cursor"]
        second = get_notifications_page(
            user_id=self.u1.id,
            limit=2,
            before_last_event_at=n3.last_event_at,
            before_id=cursor["id"],
        )

        self.assertEqual([x["id"] for x in second["items"]], [n2.id, n1.id])
        self.assertEqual(second["next_before_cursor"], self._cursor_for(n1))
        self.assertFalse(second["has_more"])

    def test_before_cursor_handles_same_last_event_at_tie_breaker(self) -> None:
        same_time = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=same_time
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=same_time
        )
        n3 = self._create_notification(
            user=self.u1, title="n3", last_event_at=same_time
        )
        n4 = self._create_notification(
            user=self.u1, title="n4", last_event_at=same_time
        )

        first = get_notifications_page(user_id=self.u1.id, limit=2)

        self.assertEqual([x["id"] for x in first["items"]], [n4.id, n3.id])
        self.assertEqual(first["next_before_cursor"], self._cursor_for(n3))

        second = get_notifications_page(
            user_id=self.u1.id,
            limit=2,
            before_last_event_at=n3.last_event_at,
            before_id=n3.id,
        )

        self.assertEqual([x["id"] for x in second["items"]], [n2.id, n1.id])
        self.assertFalse(second["has_more"])

    def test_after_cursor_fetches_newer_items_and_next_before_cursor_is_none(
        self,
    ) -> None:
        base = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=base - timedelta(minutes=3)
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=base - timedelta(minutes=2)
        )
        n3 = self._create_notification(
            user=self.u1, title="n3", last_event_at=base - timedelta(minutes=1)
        )

        res = get_notifications_page(
            user_id=self.u1.id,
            after_last_event_at=n1.last_event_at,
            after_id=n1.id,
            limit=10,
        )

        self.assertEqual([x["id"] for x in res["items"]], [n3.id, n2.id])
        self.assertIsNone(res["next_before_cursor"])
        self.assertFalse(res["has_more"])

    def test_after_cursor_handles_same_last_event_at_tie_breaker(self) -> None:
        same_time = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=same_time
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=same_time
        )
        n3 = self._create_notification(
            user=self.u1, title="n3", last_event_at=same_time
        )

        res = get_notifications_page(
            user_id=self.u1.id,
            after_last_event_at=n1.last_event_at,
            after_id=n1.id,
            limit=10,
        )

        self.assertEqual([x["id"] for x in res["items"]], [n3.id, n2.id])
        self.assertIsNone(res["next_before_cursor"])
        self.assertFalse(res["has_more"])

    def test_after_cursor_has_more_when_more_than_limit(self) -> None:
        base = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=base - timedelta(minutes=4)
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=base - timedelta(minutes=3)
        )
        n3 = self._create_notification(
            user=self.u1, title="n3", last_event_at=base - timedelta(minutes=2)
        )
        n4 = self._create_notification(
            user=self.u1, title="n4", last_event_at=base - timedelta(minutes=1)
        )

        res = get_notifications_page(
            user_id=self.u1.id,
            after_last_event_at=n1.last_event_at,
            after_id=n1.id,
            limit=2,
        )

        self.assertEqual([x["id"] for x in res["items"]], [n4.id, n3.id])
        self.assertTrue(res["has_more"])
        self.assertIsNone(res["next_before_cursor"])

    def test_updated_aggregate_with_old_id_sorts_by_last_event_at(self) -> None:
        base = timezone.now()

        old_aggregate = self._create_notification(
            user=self.u1,
            title="old-aggregate",
            notification_type=NotificationType.NEW_COMMENT,
            last_event_at=base - timedelta(hours=2),
        )
        newer_regular = self._create_notification(
            user=self.u1, title="newer-regular", last_event_at=base - timedelta(hours=1)
        )

        old_aggregate.last_event_at = base
        old_aggregate.save(update_fields=["last_event_at"])

        res = get_notifications_page(user_id=self.u1.id, limit=10)

        self.assertEqual(
            [x["id"] for x in res["items"]], [old_aggregate.id, newer_regular.id]
        )

    def test_include_read_false_filters_out_read_items(self) -> None:
        base = timezone.now()

        n1 = self._create_notification(
            user=self.u1,
            title="unread-1",
            is_read=False,
            last_event_at=base - timedelta(minutes=3),
        )
        n2 = self._create_notification(
            user=self.u1,
            title="read-1",
            is_read=True,
            last_event_at=base - timedelta(minutes=2),
        )
        n3 = self._create_notification(
            user=self.u1,
            title="unread-2",
            is_read=False,
            last_event_at=base - timedelta(minutes=1),
        )

        res = get_notifications_page(user_id=self.u1.id, include_read=False, limit=10)
        ids = [x["id"] for x in res["items"]]

        self.assertEqual(ids, [n3.id, n1.id])
        self.assertNotIn(n2.id, ids)

        for item in res["items"]:
            self.assertFalse(item["is_read"])

    def test_limit_above_max_is_capped(self) -> None:
        base = timezone.now()

        for i in range(INBOX_MAX_PAGE_SIZE + 1):
            self._create_notification(
                user=self.u1, title=f"n{i}", last_event_at=base + timedelta(seconds=i)
            )

        res = get_notifications_page(user_id=self.u1.id, limit=999999)

        self.assertEqual(len(res["items"]), INBOX_MAX_PAGE_SIZE)
        self.assertTrue(res["has_more"])

    def test_limit_below_one_defaults_to_one(self) -> None:
        base = timezone.now()

        n1 = self._create_notification(
            user=self.u1, title="n1", last_event_at=base - timedelta(minutes=2)
        )
        n2 = self._create_notification(
            user=self.u1, title="n2", last_event_at=base - timedelta(minutes=1)
        )

        res = get_notifications_page(user_id=self.u1.id, limit=0)

        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["id"], n2.id)
        self.assertTrue(res["has_more"])

    def test_payload_non_dict_serializes_as_empty_dict(self) -> None:
        n = self._create_notification(user=self.u1, title="bad-payload", payload=["x"])

        res = get_notifications_page(user_id=self.u1.id, limit=10)

        self.assertEqual(res["items"][0]["id"], n.id)
        self.assertEqual(res["items"][0]["payload"], {})

    def test_timestamp_and_last_event_at_are_isoformat_strings(self) -> None:
        created_at = timezone.now() - timedelta(days=1)
        last_event_at = timezone.now()

        n = self._create_notification(
            user=self.u1, title="n", created_at=created_at, last_event_at=last_event_at
        )

        res = get_notifications_page(user_id=self.u1.id, limit=10)
        item = res["items"][0]

        self.assertEqual(item["id"], n.id)
        self.assertIsInstance(item["timestamp"], str)
        self.assertIsInstance(item["last_event_at"], str)
        self.assertIn("T", item["timestamp"])
        self.assertIn("T", item["last_event_at"])
        self.assertEqual(item["last_event_at"], last_event_at.isoformat())
