from django.test import SimpleTestCase
from django.urls import resolve, reverse

from notifications.views import (
    NotificationDeleteView,
    NotificationReadView,
    notifications_list,
    notifications_unread_count,
)


class TestURLs(SimpleTestCase):
    def test_read_notification_url_is_resolved(self):
        url = reverse("notification-read", args=[1])
        self.assertEqual(resolve(url).func.view_class, NotificationReadView)

    def test_delete_notification_url_is_resolved(self):
        url = reverse("notification-delete", args=[1])
        self.assertEqual(resolve(url).func.view_class, NotificationDeleteView)

    def test_notifications_list_url_is_resolved(self):
        url = reverse("notifications-list")
        self.assertEqual(resolve(url).func, notifications_list)

    def test_notifications_unread_count_url_is_resolved(self):
        url = reverse("notifications-unread-count")
        self.assertEqual(resolve(url).func, notifications_unread_count)
