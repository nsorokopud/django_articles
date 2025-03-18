from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article
from users.models import User

from ..models import Notification


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.a = Article(
            title="a",
            slug="a",
            author=self.user,
            preview_text="text",
            content="content",
        )
        self.n = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="title",
            message="msg",
            link="link",
            sender=self.author,
            recipient=self.user,
        )

    def test_read_notification_view(self):
        self.assertEqual(self.n.status, Notification.Status.UNREAD)

        response = self.client.post(reverse("notification-read", args=[self.n.id]))
        self.assertEqual(response.status_code, 403)
        self.n.refresh_from_db()
        self.assertEqual(self.n.status, Notification.Status.UNREAD)

        self.client.force_login(self.user)
        response = self.client.post(reverse("notification-read", args=[self.n.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "message": "notification status was changed to READ"},
        )
        self.n.refresh_from_db()
        self.assertEqual(self.n.status, Notification.Status.READ)

    def test_delete_notification_view(self):
        res = Notification.objects.get(id=self.n.id)
        self.assertEqual(res, self.n)

        response = self.client.post(reverse("notification-delete", args=[self.n.id]))
        self.assertEqual(response.status_code, 403)
        self.n.refresh_from_db()
        res = Notification.objects.get(id=self.n.id)
        self.assertEqual(res, self.n)

        self.client.force_login(self.user)
        response = self.client.post(reverse("notification-delete", args=[self.n.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "message": "notification was deleted successfully",
                "unread_notifications_count": 0,
            },
        )
        with self.assertRaises(Notification.DoesNotExist):
            Notification.objects.get(id=self.n.id)
