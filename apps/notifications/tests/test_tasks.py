from unittest.mock import patch

from celery.contrib.testing.worker import start_worker
from channels.testing import WebsocketCommunicator

from django.db.models import signals
from django.test import TransactionTestCase
from django.urls import reverse

from articles.models import Article, ArticleComment
from articles.signals import send_article_notification, send_comment_notification
from config.celery import app
from users.models import User
from ..consumers import NotificationConsumer
from ..models import Notification
from ..tasks import (
    send_new_article_notification,
    send_new_comment_notification,
    send_notification_email,
)


class TestTasks(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        signals.post_save.disconnect(send_article_notification, sender=Article)
        signals.post_save.disconnect(send_comment_notification, sender=ArticleComment)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        signals.post_save.connect(send_article_notification, sender=Article)
        signals.post_save.connect(send_comment_notification, sender=ArticleComment)

    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.author = User.objects.create_user(username="author", email="author@test.com")
        self.author.profile.subscribers.add(self.user)
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.author,
            preview_text="text1",
            content="content1",
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.author, text="1"
        )

    async def test_send_new_article_notification(self):
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator.scope["user"] = self.user
        await communicator.connect()

        with start_worker(app, perform_ping_check=False):
            result = send_new_article_notification.delay(self.article.slug)
            self.assertEqual(result.get(), None)
            self.assertEqual(result.state, "SUCCESS")

        response = await communicator.receive_nothing()
        self.assertEqual(response, False)

        response = await communicator.receive_json_from()
        self.assertEqual(response["title"], "New Article")
        self.assertEqual(
            response["text"], f"New article from {self.author.username}: '{self.article.title}'"
        )
        self.assertEqual(response["link"], f"/articles/{self.article.slug}")

        await communicator.disconnect()

    async def test_send_new_comment_notification(self):
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator.scope["user"] = self.user
        await communicator.connect()

        with start_worker(app, perform_ping_check=False):
            result = send_new_comment_notification.delay(self.comment.id, self.user.id)
            self.assertEqual(result.get(), None)
            self.assertEqual(result.state, "SUCCESS")

        response = await communicator.receive_nothing()
        self.assertEqual(response, False)

        response = await communicator.receive_json_from()
        self.assertEqual(response["title"], "New Comment")
        self.assertEqual(
            response["text"], f"New comment on your article from {self.author.username}"
        )
        self.assertEqual(response["link"], f"/articles/{self.article.slug}")

        await communicator.disconnect()

    def test_send_notification_email(self):
        notification = Notification.objects.create(
            type=Notification.Type.NEW_ARTICLE,
            title="New Article",
            message=f"New article from {self.author.username}: '{self.article.title}'",
            link=reverse("article-details", args=(self.article.slug,)),
            sender=self.author,
            recipient=self.user,
        )

        with patch(
            "notifications.services.send_notification_email"
        ) as send_notification_email__mock, start_worker(app, perform_ping_check=False):
            result = send_notification_email.delay(notification.id)
            self.assertEqual(result.get(), None)
            self.assertEqual(result.state, "SUCCESS")
            send_notification_email__mock.assert_called_once_with(notification)
