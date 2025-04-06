from django.test import SimpleTestCase
from django.urls import resolve, reverse

from notifications.views import DeleteNotificationView, ReadNotificationView


class TestURLs(SimpleTestCase):
    def test_read_notification_url_is_resolved(self):
        url = reverse("notification-read", args=[1])
        self.assertEqual(resolve(url).func.view_class, ReadNotificationView)

    def test_delete_notification_url_is_resolved(self):
        url = reverse("notification-delete", args=[1])
        self.assertEqual(resolve(url).func.view_class, DeleteNotificationView)
