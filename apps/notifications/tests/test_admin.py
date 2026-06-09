from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification, NotificationType
from users.models import User


class TestNotificationAdmin(TestCase):
    def setUp(self):
        self.staff = User.objects.create(
            username="staff", email="staff@test.com", is_staff=True
        )
        self.recipient = User.objects.create(
            username="recipient", email="recipient@test.com"
        )
        self.sender = User.objects.create(username="sender", email="sender@test.com")

        view_permission = Permission.objects.get(codename="view_notification")
        self.staff.user_permissions.add(view_permission)

        self.notification = Notification.objects.create(
            recipient=self.recipient,
            sender=self.sender,
            notification_type=NotificationType.SYSTEM,
            title="Original title",
            body="Original body",
            payload={"kind": "test"},
            dedupe_key="test-dedupe",
            aggregate_key="test-aggregate",
        )

        self.client.force_login(self.staff)

    def test_staff_can_view_notification_changelist(self):
        response = self.client.get(
            reverse("admin:notifications_notification_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original title")

    def test_staff_can_view_notification_detail_read_only(self):
        response = self.client.get(
            reverse(
                "admin:notifications_notification_change", args=[self.notification.id]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original title")
        self.assertNotContains(response, 'name="title"')

    def test_staff_cannot_add_notification(self):
        response = self.client.get(reverse("admin:notifications_notification_add"))

        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_change_notification_with_post(self):
        response = self.client.post(
            reverse(
                "admin:notifications_notification_change", args=[self.notification.id]
            ),
            {
                "recipient": self.recipient.id,
                "sender": self.sender.id,
                "notification_type": NotificationType.SYSTEM,
                "level": Notification.Level.ERROR,
                "title": "Changed title",
                "body": "Changed body",
                "payload": "{}",
                "dedupe_key": "changed-dedupe",
                "aggregate_key": "changed-aggregate",
                "_save": "Save",
            },
        )

        self.notification.refresh_from_db()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.notification.title, "Original title")
        self.assertEqual(self.notification.body, "Original body")
        self.assertEqual(self.notification.dedupe_key, "test-dedupe")

    def test_staff_cannot_delete_notification(self):
        response = self.client.post(
            reverse(
                "admin:notifications_notification_delete", args=[self.notification.id]
            ),
            {"post": "yes"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Notification.objects.filter(id=self.notification.id).exists())
