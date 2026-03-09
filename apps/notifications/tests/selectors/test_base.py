from django.test import TestCase

from notifications.models import Notification, NotificationType
from notifications.selectors.base import (
    find_notifications_by_user,
    get_unread_notifications_count_by_user,
)
from users.models import User


class TestBaseSelectors(TestCase):
    def setUp(self) -> None:
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_find_notifications_by_user_filters_by_recipient_id(self) -> None:
        n1 = Notification.objects.create(
            notification_type=NotificationType.NEW_ARTICLE,
            title="New Article",
            body="body1",
            payload={"link": "/x/"},
            sender=self.author,
            recipient=self.user,
        )
        n2 = Notification.objects.create(
            notification_type=NotificationType.NEW_COMMENT,
            title="New Comment",
            body="body2",
            payload={"link": "/y/"},
            sender=self.author,
            recipient=self.user,
        )
        Notification.objects.create(
            notification_type=NotificationType.NEW_ARTICLE,
            title="Other",
            body="body3",
            payload={"link": "/z/"},
            sender=self.user,
            recipient=self.author,
        )

        qs = find_notifications_by_user(self.user.id)
        self.assertCountEqual(list(qs), [n1, n2])

    def test_get_unread_notifications_count_by_user_reads_cached_user_field(
        self,
    ) -> None:
        User.objects.filter(id=self.user.id).update(unread_notifications_count=12345)
        self.assertEqual(get_unread_notifications_count_by_user(self.user.id), 12345)

    def test_get_unread_notifications_count_by_user_missing_user_returns_0(
        self,
    ) -> None:
        self.assertEqual(get_unread_notifications_count_by_user(999999), 0)
