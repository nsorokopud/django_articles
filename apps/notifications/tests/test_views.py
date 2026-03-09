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
            username="recipient",
            email="recipient@test.com",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@test.com",
        )
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@test.com",
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

    def test_list_view_default_returns_items(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("items", data)
        self.assertIsInstance(data["items"], list)
        self.assertGreaterEqual(len(data["items"]), 1)

        first = data["items"][0]
        self.assertEqual(first["id"], self.n.id)
        self.assertEqual(first["title"], "title")
        self.assertEqual(first["body"], "msg")
        self.assertEqual(first["payload"], {"link": "/x/"})
        self.assertIn("timestamp", first)
        self.assertIn("is_read", first)

    def test_list_view_include_read_false_returns_only_unread(self) -> None:
        Notification.objects.filter(id=self.n.id).update(read_at=timezone.now())

        n2 = Notification.objects.create(
            notification_type=NotificationType.SYSTEM,
            title="t2",
            body="b2",
            payload={},
            sender=self.sender,
            recipient=self.recipient,
        )

        self.client.force_login(self.recipient)
        url = reverse("notifications-list")
        res = self.client.get(url + "?include_read=0")
        self.assertEqual(res.status_code, 200)

        items = res.json()["items"]
        self.assertEqual([x["id"] for x in items], [n2.id])

    def test_list_view_invalid_limit_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url, {"limit": "abc"})

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "invalid integer for 'limit'"})

    def test_list_view_invalid_after_id_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url, {"after_id": "abc"})

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "invalid integer for 'after_id'"})

    def test_list_view_invalid_before_id_returns_400(self) -> None:
        self.client.force_login(self.recipient)
        url = reverse("notifications-list")

        res = self.client.get(url, {"before_id": "abc"})

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"error": "invalid integer for 'before_id'"})
