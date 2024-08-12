from datetime import datetime
from unittest.mock import call, patch

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from articles.models import Article, ArticleComment
from ..consumers import NotificationConsumer
from ..models import Notification
from ..services import (
    create_new_article_notification,
    create_new_comment_notification,
    find_notifications_by_user,
    send_new_article_notification,
    send_new_comment_notification,
    _send_notification,
)


class TestServices(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author")
        self.user = User.objects.create_user(username="user")
        self.a = Article(
            title="a",
            slug="a",
            author=self.author,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

    def test_send_new_article_notification(self):
        user1 = User.objects.create_user(username="user1")
        user2 = User.objects.create_user(username="user2")
        self.author.profile.subscribers.add(user1)
        self.author.profile.subscribers.add(user2)
        n1 = Notification(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=user1,
            created_at=datetime.now(),
        )
        n2 = Notification(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=user2,
            created_at=datetime.now(),
        )

        with patch(
            "notifications.services.create_new_article_notification", side_effect=[n1, n2]
        ) as create_new_article_notification__mock, patch(
            "notifications.services._send_notification",
        ) as _send_notification__mock:

            send_new_article_notification(self.a)

            create_new_article_notification__mock.assert_has_calls(
                [call(self.a, user1), call(self.a, user2)], any_order=True
            )
            _send_notification__mock.assert_has_calls(
                [call(n1, user1.username), call(n2, user2.username)], any_order=True
            )

    def test_send_new_comment_notification(self):
        c = ArticleComment(article=self.a, author=self.user, text="1")

        n = Notification(
            type=Notification.Type.NEW_COMMENT,
            title="New Comment",
            message=f"New comment on your article from {self.author.username}",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.user,
            recipient=self.author,
            created_at=datetime.now(),
        )

        with patch(
            "notifications.services.create_new_comment_notification", return_value=n
        ) as create_new_comment_notification__mock, patch(
            "notifications.services._send_notification",
        ) as _send_notification__mock:

            send_new_comment_notification(c, self.author)

            create_new_comment_notification__mock.assert_called_once_with(c, self.author)
            _send_notification__mock.assert_called_once_with(n, self.author.username)

    async def test__send_notification(self):
        n = await database_sync_to_async(Notification.objects.create)(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator.scope["user"] = self.user
        await communicator.connect()

        await sync_to_async(_send_notification)(n, self.user.username)

        response = await communicator.receive_json_from()
        self.assertEqual(
            response,
            {
                "id": n.id,
                "title": n.title,
                "text": n.message,
                "link": n.link,
                "timestamp": n.created_at.isoformat(),
            },
        )

        await communicator.disconnect()

    def test_create_new_article_notification(self):
        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 0)

        create_new_article_notification(self.a, self.user)

        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 1)

        n = Notification.objects.get(sender=self.author, recipient=self.user)
        self.assertEqual(n.type, Notification.Type.NEW_ARTICLE)
        self.assertEqual(n.status, Notification.Status.UNREAD)
        self.assertEqual(n.title, "New Article")
        self.assertEqual(n.message, f"New article from {self.author.username}: '{self.a.title}'")
        self.assertEqual(n.link, reverse("article-details", args=(self.a.slug,)))

    def test_create_new_comment_notification(self):
        c = ArticleComment(article=self.a, author=self.user, text="1")

        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 0)

        create_new_comment_notification(c, self.author)

        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 1)

        n = Notification.objects.get(sender=self.user, recipient=self.author)
        self.assertEqual(n.type, Notification.Type.NEW_COMMENT)
        self.assertEqual(n.status, Notification.Status.UNREAD)
        self.assertEqual(n.title, "New Comment")
        self.assertEqual(n.message, f"New comment on your article from {self.user.username}")
        self.assertEqual(n.link, reverse("article-details", args=(self.a.slug,)))

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
