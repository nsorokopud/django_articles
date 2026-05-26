from datetime import timedelta

from django.conf import settings
from django.shortcuts import resolve_url
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification, NotificationType
from users.models import User


class TestNotificationViews(TestCase):
    def setUp(self) -> None:
        self.client = Client()

        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@test.com"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com"
        )
        self.sender = User.objects.create_user(
            username="sender", email="sender@test.com"
        )

        self.n = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="title",
            body="msg",
            payload={"link": "/x/"},
            sender=self.sender,
            recipient=self.recipient,
        )

        User.objects.filter(id=self.recipient.id).update(unread_notifications_count=1)

    def test_read_requires_auth(self) -> None:
        url = reverse("notification-read", args=[self.n.id])
        res = self.client.post(url)

        self.assertRedirects(
            res,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False,
        )

        self.n.refresh_from_db()
        self.assertIsNone(self.n.read_at)

    def test_read_only_marks_for_recipient(self) -> None:
        url = reverse("notification-read", args=[self.n.id])

        self.client.force_login(self.other_user)
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["changed"])
        self.assertIn("unread_notifications_count", data)

        self.n.refresh_from_db()
        self.assertIsNone(self.n.read_at)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

    def test_read_marks_read_and_decrements_unread(self) -> None:
        url = reverse("notification-read", args=[self.n.id])

        self.client.force_login(self.recipient)
        before = timezone.now()

        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["changed"])
        self.assertEqual(data["unread_notifications_count"], 0)

        self.n.refresh_from_db()
        self.assertIsNotNone(self.n.read_at)
        assert self.n.read_at is not None
        self.assertGreaterEqual(self.n.read_at, before)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 0)

    def test_read_is_idempotent_second_call_changed_false(self) -> None:
        url = reverse("notification-read", args=[self.n.id])
        self.client.force_login(self.recipient)

        res1 = self.client.post(url)
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()["changed"])

        res2 = self.client.post(url)
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(res2.json()["changed"])

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 0)

    def test_delete_requires_auth(self) -> None:
        url = reverse("notification-delete", args=[self.n.id])
        res = self.client.post(url)

        self.assertRedirects(
            res,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False,
        )

        self.assertTrue(Notification.objects.filter(id=self.n.id).exists())

    def test_delete_only_deletes_for_recipient(self) -> None:
        url = reverse("notification-delete", args=[self.n.id])

        self.client.force_login(self.other_user)
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["deleted"])

        self.assertTrue(Notification.objects.filter(id=self.n.id).exists())

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

    def test_delete_unread_decrements_unread(self) -> None:
        url = reverse("notification-delete", args=[self.n.id])
        self.client.force_login(self.recipient)

        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["deleted"])
        self.assertEqual(data["unread_notifications_count"], 0)

        self.assertFalse(Notification.objects.filter(id=self.n.id).exists())

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 0)

    def test_delete_read_does_not_decrement_unread(self) -> None:
        Notification.objects.filter(id=self.n.id).update(read_at=timezone.now())
        self.recipient.refresh_from_db()
        self.recipient.unread_notifications_count = 0
        self.recipient.save(update_fields=["unread_notifications_count"])

        url = reverse("notification-delete", args=[self.n.id])
        self.client.force_login(self.recipient)

        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertTrue(data["deleted"])
        self.assertEqual(data["unread_notifications_count"], 0)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 0)

    def test_unread_count_view(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-unread-count")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"unread": 1})


class TestNotificationListView(TestCase):
    def setUp(self) -> None:
        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@test.com"
        )
        self.sender = User.objects.create_user(
            username="sender", email="sender@test.com"
        )

        self.now = timezone.now()

        self.n = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="title",
            body="msg",
            payload={"link": "/x/"},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now,
        )

    def test_default_returns_items(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("items", data)
        self.assertIn("next_before_cursor", data)
        self.assertIn("has_more", data)

        self.assertIsInstance(data["items"], list)
        self.assertGreaterEqual(len(data["items"]), 1)

        first = data["items"][0]
        self.assertEqual(first["id"], self.n.id)
        self.assertEqual(first["title"], "title")
        self.assertEqual(first["body"], "msg")
        self.assertEqual(first["payload"], {"link": "/x/"})
        self.assertIn("timestamp", first)
        self.assertIn("last_event_at", first)
        self.assertIn("is_read", first)
        self.assertFalse(first["is_read"])

        self.assertEqual(data["next_before_cursor"]["id"], self.n.id)
        self.assertEqual(
            data["next_before_cursor"]["last_event_at"], first["last_event_at"]
        )

    def test_orders_by_last_event_at_then_id(self) -> None:
        older = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="older",
            body="older",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now - timedelta(minutes=10),
        )
        newer = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="newer",
            body="newer",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now + timedelta(minutes=10),
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)

        ids = [item["id"] for item in res.json()["items"]]
        self.assertEqual(ids, [newer.id, self.n.id, older.id])

    def test_orders_same_last_event_at_by_id_desc(self) -> None:
        same_time = self.now + timedelta(minutes=20)

        n2 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="n2",
            body="n2",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=same_time,
        )
        n3 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="n3",
            body="n3",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=same_time,
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)

        ids = [item["id"] for item in res.json()["items"]]
        self.assertEqual(ids[:2], [n3.id, n2.id])

    def test_include_read_false_returns_only_unread(self) -> None:
        Notification.objects.filter(id=self.n.id).update(read_at=timezone.now())

        n2 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="t2",
            body="b2",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now + timedelta(minutes=1),
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url + "?include_read=0")

        self.assertEqual(res.status_code, 200)

        items = res.json()["items"]
        self.assertEqual([x["id"] for x in items], [n2.id])
        self.assertFalse(items[0]["is_read"])

    def test_before_cursor_returns_older_items(self) -> None:
        oldest = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="oldest",
            body="oldest",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now - timedelta(minutes=20),
        )
        middle = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="middle",
            body="middle",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now - timedelta(minutes=10),
        )
        newest = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="newest",
            body="newest",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now + timedelta(minutes=10),
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        first_page = self.client.get(url, {"limit": 2})
        self.assertEqual(first_page.status_code, 200)

        first_data = first_page.json()
        self.assertEqual(
            [item["id"] for item in first_data["items"]], [newest.id, self.n.id]
        )

        cursor = first_data["next_before_cursor"]
        self.assertEqual(cursor["id"], self.n.id)

        second_page = self.client.get(
            url,
            {
                "limit": 2,
                "before_last_event_at": cursor["last_event_at"],
                "before_id": cursor["id"],
            },
        )
        self.assertEqual(second_page.status_code, 200)

        second_data = second_page.json()
        self.assertEqual(
            [item["id"] for item in second_data["items"]], [middle.id, oldest.id]
        )

    def test_before_cursor_handles_same_last_event_at(self) -> None:
        same_time = self.now + timedelta(minutes=30)

        n2 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="n2",
            body="n2",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=same_time,
        )
        n3 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="n3",
            body="n3",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=same_time,
        )
        n4 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="n4",
            body="n4",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=same_time,
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        first_page = self.client.get(url, {"limit": 2})
        self.assertEqual(first_page.status_code, 200)

        first_data = first_page.json()
        self.assertEqual([item["id"] for item in first_data["items"]], [n4.id, n3.id])

        cursor = first_data["next_before_cursor"]

        second_page = self.client.get(
            url,
            {
                "limit": 2,
                "before_last_event_at": cursor["last_event_at"],
                "before_id": cursor["id"],
            },
        )
        self.assertEqual(second_page.status_code, 200)

        second_data = second_page.json()
        self.assertEqual(
            [item["id"] for item in second_data["items"]], [n2.id, self.n.id]
        )

    def test_after_cursor_returns_newer_items(self) -> None:
        older = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="older",
            body="older",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now - timedelta(minutes=10),
        )
        newer = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="newer",
            body="newer",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=self.now + timedelta(minutes=10),
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(
            url,
            {
                "after_last_event_at": self.n.last_event_at.isoformat(),
                "after_id": self.n.id,
            },
        )

        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual([item["id"] for item in data["items"]], [newer.id])
        self.assertNotIn(older.id, [item["id"] for item in data["items"]])

    def test_after_cursor_handles_same_last_event_at(self) -> None:
        same_time = self.now + timedelta(minutes=10)

        n2 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="n2",
            body="n2",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=same_time,
        )
        n3 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="n3",
            body="n3",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
            last_event_at=same_time,
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(
            url, {"after_last_event_at": same_time.isoformat(), "after_id": n2.id}
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual([item["id"] for item in res.json()["items"]], [n3.id])

    def test_invalid_limit_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url, {"limit": "abc"})

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "invalid integer for 'limit'"})

    def test_invalid_after_id_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url, {"after_id": "abc"})

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "invalid integer for 'after_id'"})

    def test_invalid_before_id_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url, {"before_id": "abc"})

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "invalid integer for 'before_id'"})

    def test_invalid_after_last_event_at_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(
            url, {"after_last_event_at": "not-a-date", "after_id": self.n.id}
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "Invalid after_last_event_at."})

    def test_invalid_before_last_event_at_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(
            url, {"before_last_event_at": "not-a-date", "before_id": self.n.id}
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "Invalid before_last_event_at."})

    def test_after_cursor_requires_both_fields(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(
            url, {"after_last_event_at": self.n.last_event_at.isoformat()}
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.json(),
            {
                "error": (
                    "after cursor requires after_last_event_at and positive after_id"
                )
            },
        )

    def test_before_cursor_requires_both_fields(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url, {"before_id": self.n.id})

        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.json(),
            {
                "error": (
                    "before cursor requires before_last_event_at and positive before_id"
                )
            },
        )

    def test_rejects_after_and_before_cursor_together(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(
            url,
            {
                "after_last_event_at": self.n.last_event_at.isoformat(),
                "after_id": self.n.id,
                "before_last_event_at": self.n.last_event_at.isoformat(),
                "before_id": self.n.id,
            },
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.json(), {"error": "Use either after cursor or before cursor, not both."}
        )
