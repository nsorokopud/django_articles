from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.core import mail
from django.db.models import signals
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from articles.models import Article, ArticleComment
from articles.signals import send_article_notification, send_comment_notification
from users.models import User

from ..consumers import NotificationConsumer
from ..models import Notification
from ..tasks import (
    send_new_article_notification,
    send_new_comment_notification,
    send_notification_email,
)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestTasks(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        signals.post_save.disconnect(send_article_notification, sender=Article)
        signals.post_save.disconnect(send_comment_notification, sender=ArticleComment)

    @classmethod
    def tearDownClass(cls):
        signals.post_save.connect(send_article_notification, sender=Article)
        signals.post_save.connect(send_comment_notification, sender=ArticleComment)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
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
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        result = await sync_to_async(send_new_article_notification.delay)(
            self.article.slug
        )
        await sync_to_async(result.get)(timeout=5)
        self.assertEqual(result.state, "SUCCESS")

        response = await communicator.receive_json_from()
        self.assertEqual(response["title"], "New Article")
        self.assertEqual(
            response["text"],
            (
                f"New article from <strong>{self.author.username}</strong>: "
                f'<strong>"{self.article.title}"</strong>'
            ),
        )
        self.assertEqual(response["link"], f"/articles/{self.article.slug}")

        await communicator.disconnect()

    async def test_send_new_comment_notification(self):
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        result = await sync_to_async(send_new_comment_notification.delay)(
            self.comment.id, self.user.id
        )
        await sync_to_async(result.get)(timeout=5)
        self.assertEqual(result.state, "SUCCESS")

        response = await communicator.receive_json_from()
        self.assertEqual(response["title"], "New Comment")
        self.assertEqual(
            response["text"],
            (
                f'New comment on your article <strong>"{self.article.title}"</strong> '
                f"from <strong>{self.author.username}</strong>"
            ),
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
        self.assertEqual(len(mail.outbox), 0)

        result = send_notification_email.delay(notification.id)
        self.assertIsNone(result.get(timeout=5))
        self.assertEqual(result.state, "SUCCESS")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), [self.user.email])
