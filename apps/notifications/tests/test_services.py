from datetime import datetime
from unittest.mock import call, patch

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from django.core import mail
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from articles.models import Article, ArticleComment
from config.settings import DOMAIN_NAME, SCHEME
from users.models import User
from ..consumers import NotificationConsumer
from ..models import Notification
from ..services import (
    create_new_article_notification,
    create_new_comment_notification,
    delete_notification,
    find_notifications_by_user,
    get_notification_by_id,
    get_unread_notifications_count_by_user,
    mark_notification_as_read,
    send_new_article_notification,
    send_new_comment_notification,
    send_notification_email,
    _send_notification,
)


class TestServices(TransactionTestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", email="author@test.com")
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.a = Article(
            title="a",
            slug="a",
            author=self.author,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

    def test_send_new_article_notification(self):
        user1 = User.objects.create_user(username="user1", email="user1@test.com")
        user2 = User.objects.create_user(username="user2", email="user2@test.com")
        user2.profile.notification_emails_allowed = False
        user2.profile.save()
        self.author.profile.subscribers.add(user1)
        self.author.profile.subscribers.add(user2)
        n1 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=user1,
            created_at=datetime.now(),
        )
        n2 = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=user2,
            created_at=datetime.now(),
        )

        user1.refresh_from_db()
        user2.refresh_from_db()
        self.assertTrue(user1.profile.notification_emails_allowed)
        self.assertFalse(user2.profile.notification_emails_allowed)

        with patch(
            "notifications.services.create_new_article_notification", side_effect=[n1, n2]
        ) as create_new_article_notification__mock, patch(
            "notifications.services._send_notification",
        ) as _send_notification__mock, patch(
            "notifications.tasks.send_notification_email.delay"
        ) as send_notification_email__mock:

            send_new_article_notification(self.a)

            create_new_article_notification__mock.assert_has_calls(
                [call(self.a, user1), call(self.a, user2)], any_order=True
            )
            _send_notification__mock.assert_has_calls(
                [call(n1, user1.username), call(n2, user2.username)], any_order=True
            )
            self.assertEqual(send_notification_email__mock.call_args_list, [call(n1.id)])

    def test_send_new_comment_notification(self):
        author1 = User.objects.create_user(username="author1", email="author1@test.com")
        a = Article(title="a", slug="a", author=author1, preview_text="a", content="a")
        c = ArticleComment(article=a, author=self.user, text="1")

        n = Notification.objects.create(
            type=Notification.Type.NEW_COMMENT,
            title="New Comment",
            message=f"New comment on your article from {author1.username}",
            link=reverse("article-details", args=(a.slug,)),
            sender=self.user,
            recipient=author1,
        )

        with patch(
            "notifications.services.create_new_comment_notification", return_value=n
        ) as create_new_comment_notification__mock, patch(
            "notifications.services._send_notification",
        ) as _send_notification__mock, patch(
            "notifications.tasks.send_notification_email.delay"
        ) as send_notification_email__mock:

            send_new_comment_notification(c, author1)

            create_new_comment_notification__mock.assert_called_once_with(c, author1)
            _send_notification__mock.assert_called_once_with(n, author1.username)
            self.assertEqual(send_notification_email__mock.call_args_list, [call(n.id)])

        author1.profile.notification_emails_allowed = False
        author1.profile.save()
        author1.refresh_from_db()
        self.assertFalse(author1.profile.notification_emails_allowed)

        with patch(
            "notifications.tasks.send_notification_email.delay"
        ) as send_notification_email__mock:
            send_new_comment_notification(c, author1)
            self.assertEqual(send_notification_email__mock.call_args_list, [])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_notification_email(self):
        notification = Notification(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
            created_at=datetime.now(),
        )

        self.assertEqual(len(mail.outbox), 0)

        send_notification_email(notification)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ["user@test.com"])
        self.assertEqual(mail.outbox[0].subject, "New Article")
        expected_body = (
            f"\n{notification.message}. "
            f'<a href="{SCHEME}://{DOMAIN_NAME}{notification.link}">'
            "Check it out</a>\n\n"
        )
        self.assertEqual(mail.outbox[0].body, expected_body)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)

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

    def test_mark_notification_as_read(self):
        n = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        self.assertEqual(n.status, Notification.Status.UNREAD)

        mark_notification_as_read(n)
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.READ)

    def test_delete_notification(self):
        n = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.a.title}'",
            link=reverse("article-details", args=(self.a.slug,)),
            sender=self.author,
            recipient=self.user,
        )
        self.assertEqual(Notification.objects.get(id=n.id), n)

        delete_notification(n)
        with self.assertRaises(Notification.DoesNotExist):
            Notification.objects.get(id=n.id)

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
