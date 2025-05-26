from contextlib import ExitStack

from celery.contrib.testing.worker import start_worker
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from articles.models import Article, ArticleComment
from config.celery import app
from notifications.models import Notification
from users.models import Profile, User

from ..consumers import NotificationConsumer


class TestNotificationIntegration(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._exit_stack = ExitStack()
        cls.celery_worker = cls._exit_stack.enter_context(
            start_worker(app, perform_ping_check=False)
        )

    @classmethod
    def tearDownClass(cls):
        cls._exit_stack.close()
        super().tearDownClass()

    async def test_client_receives_notification_upon_new_article_creation(self):
        user1 = await database_sync_to_async(User.objects.create_user)(
            username="u1", email="u1@test.com"
        )
        await database_sync_to_async(Profile.objects.get_or_create)(user=user1)
        user2 = await database_sync_to_async(User.objects.create_user)(
            username="u2", email="u2@test.com"
        )
        await database_sync_to_async(Profile.objects.get_or_create)(user=user2)
        user3 = await database_sync_to_async(User.objects.create_user)(
            username="u3", email="u3@test.com"
        )
        author = await database_sync_to_async(User.objects.create_user)(
            username="author", email="author@test.com"
        )
        await database_sync_to_async(Profile.objects.get_or_create)(user=author)

        communicator1 = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator1.scope["user"] = user1
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)

        communicator2 = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator2.scope["user"] = user2
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected2)

        communicator3 = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator3.scope["user"] = user3
        connected3, _ = await communicator3.connect()
        self.assertTrue(connected3)

        await database_sync_to_async(author.subscribers.add)(user1)
        await database_sync_to_async(author.subscribers.add)(user2)

        a = await database_sync_to_async(Article.objects.create)(
            title="a1",
            slug="a1",
            author=author,
            preview_text="text1",
            content="content1",
        )

        response1 = await communicator1.receive_json_from(timeout=2)
        response2 = await communicator2.receive_json_from(timeout=2)
        response3 = await communicator3.receive_nothing()
        self.assertTrue(response3)

        self.assertEqual(response1["title"], "New Article")
        self.assertEqual(
            response1["text"],
            (
                f"New article from <strong>{author.username}</strong>: "
                f'<strong>"{a.title}"</strong>'
            ),
        )
        self.assertEqual(response1["link"], f"/articles/{a.slug}")

        self.assertEqual(response2["title"], "New Article")
        self.assertEqual(
            response2["text"],
            (
                f"New article from <strong>{author.username}</strong>: "
                f'<strong>"{a.title}"</strong>'
            ),
        )
        self.assertEqual(response2["link"], f"/articles/{a.slug}")

        self.assertNotEqual(response1["id"], response2["id"])

        await communicator1.disconnect()
        await communicator2.disconnect()
        await communicator3.disconnect()

    async def test_client_receives_notification_upon_new_comment_creation(self):
        author = await database_sync_to_async(User.objects.create_user)(
            username="author"
        )
        await database_sync_to_async(Profile.objects.get_or_create)(user=author)

        article = await database_sync_to_async(Article.objects.create)(
            title="a",
            slug="a",
            author=author,
            preview_text="text1",
            content="content1",
        )

        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = author
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        c = await database_sync_to_async(ArticleComment.objects.create)(
            article=article, author=author, text="1"
        )

        response = await communicator.receive_json_from(timeout=2)

        last_notification = await database_sync_to_async(Notification.objects.last)()

        self.assertEqual(response["id"], last_notification.id)
        self.assertEqual(response["title"], "New Comment")
        self.assertEqual(
            response["text"],
            (
                f'New comment on your article <strong>"{c.article.title}"</strong> '
                f"from <strong>{c.author.username}</strong>"
            ),
        )
        self.assertEqual(response["link"], "/articles/a")

        await communicator.disconnect()
