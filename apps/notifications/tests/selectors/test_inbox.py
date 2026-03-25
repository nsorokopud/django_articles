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
    ) -> Notification:
        if payload is None:
            payload = {"link": "/x/"}
        if created_at is None:
            created_at = timezone.now()

        n = Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.SYSTEM,
            level=Notification.Level.INFO,
            title=title,
            body=f"body:{title}",
            payload=payload,
            created_at=created_at,
        )
        if is_read:
            n.read_at = timezone.now()
            n.save(update_fields=["read_at"])
        return n

    def test_returns_empty_when_user_has_no_notifications(self) -> None:
        res = get_notifications_page(user_id=self.u1.id)
        self.assertEqual(res["items"], [])
        self.assertIsNone(res["next_before_id"])
        self.assertFalse(res["has_more"])

    def test_initial_page_orders_newest_first_and_sets_next_before_id(self) -> None:
        n1 = self._create_notification(user=self.u1, title="n1")
        n2 = self._create_notification(user=self.u1, title="n2")
        n3 = self._create_notification(user=self.u1, title="n3")

        res = get_notifications_page(user_id=self.u1.id, limit=2)

        self.assertEqual([x["id"] for x in res["items"]], [n3.id, n2.id])
        self.assertEqual(res["next_before_id"], n2.id)
        self.assertTrue(res["has_more"])

        item = res["items"][0]
        self.assertIn("timestamp", item)
        self.assertIn("payload", item)
        self.assertEqual(item["is_read"], False)

        # ensure user isolation (create for u2 does not affect)
        self._create_notification(user=self.u2, title="other")
        res2 = get_notifications_page(user_id=self.u1.id, limit=10)
        self.assertEqual([x["id"] for x in res2["items"]], [n3.id, n2.id, n1.id])

    def test_before_id_paginates_older_items(self) -> None:
        n1 = self._create_notification(user=self.u1, title="n1")
        n2 = self._create_notification(user=self.u1, title="n2")
        n3 = self._create_notification(user=self.u1, title="n3")
        n4 = self._create_notification(user=self.u1, title="n4")

        # initial: n4, n3
        first = get_notifications_page(user_id=self.u1.id, limit=2)
        self.assertEqual([x["id"] for x in first["items"]], [n4.id, n3.id])
        self.assertEqual(first["next_before_id"], n3.id)
        self.assertTrue(first["has_more"])

        # older: ids < n3.id => n2, n1
        second = get_notifications_page(
            user_id=self.u1.id, limit=2, before_id=first["next_before_id"]
        )
        self.assertEqual([x["id"] for x in second["items"]], [n2.id, n1.id])
        self.assertEqual(second["next_before_id"], n1.id)
        self.assertFalse(second["has_more"])

    def test_after_id_fetches_newer_items_and_next_before_id_is_none(self) -> None:
        n1 = self._create_notification(user=self.u1, title="n1")
        n2 = self._create_notification(user=self.u1, title="n2")
        n3 = self._create_notification(user=self.u1, title="n3")

        res = get_notifications_page(user_id=self.u1.id, after_id=n1.id, limit=10)

        self.assertEqual([x["id"] for x in res["items"]], [n3.id, n2.id])
        self.assertIsNone(res["next_before_id"])
        self.assertFalse(res["has_more"])

    def test_after_id_has_more_when_more_than_limit(self) -> None:
        n1 = self._create_notification(user=self.u1, title="n1")
        n2 = self._create_notification(user=self.u1, title="n2")
        n3 = self._create_notification(user=self.u1, title="n3")
        n4 = self._create_notification(user=self.u1, title="n4")

        res = get_notifications_page(user_id=self.u1.id, after_id=n1.id, limit=2)
        self.assertEqual([x["id"] for x in res["items"]], [n4.id, n3.id])
        self.assertTrue(res["has_more"])
        self.assertIsNone(res["next_before_id"])

    def test_include_read_false_filters_out_read_items(self) -> None:
        n1 = self._create_notification(user=self.u1, title="unread-1", is_read=False)
        n2 = self._create_notification(user=self.u1, title="read-1", is_read=True)
        n3 = self._create_notification(user=self.u1, title="unread-2", is_read=False)

        res = get_notifications_page(user_id=self.u1.id, include_read=False, limit=10)
        ids = [x["id"] for x in res["items"]]
        self.assertEqual(ids, [n3.id, n1.id])
        self.assertNotIn(n2.id, ids)

        for item in res["items"]:
            self.assertFalse(item["is_read"])

    def test_limit_above_max_is_capped(self) -> None:
        for i in range(INBOX_MAX_PAGE_SIZE + 1):
            self._create_notification(user=self.u1, title=f"n{i}")

        res = get_notifications_page(user_id=self.u1.id, limit=999999)
        self.assertEqual(len(res["items"]), INBOX_MAX_PAGE_SIZE)
        self.assertTrue(res["has_more"])

    def test_limit_below_one_defaults_to_one(self) -> None:
        n1 = self._create_notification(user=self.u1, title="n1")
        n2 = self._create_notification(user=self.u1, title="n2")

        res = get_notifications_page(user_id=self.u1.id, limit=0)
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["id"], n2.id)
        self.assertTrue(res["has_more"])

    def test_payload_non_dict_serializes_as_empty_dict(self) -> None:
        n = self._create_notification(user=self.u1, title="bad-payload", payload=["x"])

        res = get_notifications_page(user_id=self.u1.id, limit=10)
        self.assertEqual(res["items"][0]["id"], n.id)
        self.assertEqual(res["items"][0]["payload"], {})

    def test_timestamp_is_isoformat_string(self) -> None:
        ts = timezone.now() - timedelta(days=1)
        n = self._create_notification(user=self.u1, title="n", created_at=ts)

        res = get_notifications_page(user_id=self.u1.id, limit=10)
        item = res["items"][0]
        self.assertEqual(item["id"], n.id)
        self.assertIsInstance(item["timestamp"], str)
        self.assertIn("T", item["timestamp"])
