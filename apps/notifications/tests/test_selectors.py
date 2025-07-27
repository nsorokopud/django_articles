from django.test import TestCase
from django.urls import reverse

from articles.models import Article
from users.models import User

from ..models import Notification
from ..selectors import (
    find_notifications_by_user,
    get_notification_by_id,
    get_unread_notifications_count_by_user,
)


class TestSelectors(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.a = Article(
            title="a",
            slug="a",
            author=self.author,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

    def test_get_notification_by_id(self):
        n1 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        n2 = Notification.objects.create(
            type=Notification.Type.NEW_COMMENT,
            title="New Comment",
            message=f"New comment on your article from {self.user.username}",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.user,
            recipient=self.author,
        )

        res1 = get_notification_by_id(n1.id)
        self.assertEqual(res1, n1)
        self.assertEqual(res1, Notification.objects.get(id=n1.id))

        res2 = get_notification_by_id(n2.id)
        self.assertEqual(res2, n2)
        self.assertEqual(res2, Notification.objects.get(id=n2.id))

        with self.assertRaises(Notification.DoesNotExist):
            get_notification_by_id(-1)

    def test_find_notifications_by_user(self):
        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 0)

        n1 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        n2 = Notification.objects.create(
            type=Notification.Type.NEW_COMMENT,
            title="New Comment",
            message=f"New comment on your article from {self.author.username}",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        n3 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.user.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.user,
            recipient=self.author,
        )

        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 3)

        res = find_notifications_by_user(self.user)
        self.assertCountEqual(res, [n1, n2])

    def test_get_unread_notifications_count_by_user(self):
        n1 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        n2 = Notification.objects.create(
            type=Notification.Type.NEW_COMMENT,
            title="New Comment",
            message=f"New comment on your article from {self.author.username}",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        n3 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
            status=Notification.Status.READ,
        )
        n4 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.user.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.user,
            recipient=self.author,
            status=Notification.Status.UNREAD,
        )

        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 4)

        unread_notifications_count = Notification.objects.filter(
            status=Notification.Status.UNREAD
        ).count()
        self.assertEqual(unread_notifications_count, 3)

        unread_notifications_for_user_count = Notification.objects.filter(
            status=Notification.Status.UNREAD, recipient=self.user
        ).count()
        self.assertEqual(unread_notifications_for_user_count, 2)

        res = get_unread_notifications_count_by_user(self.user)
        self.assertEqual(res, 2)
