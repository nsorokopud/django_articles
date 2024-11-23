from asyncio.exceptions import TimeoutError
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from users.models import User
from ..consumers import NotificationConsumer


class TestNotificationConsumer(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", email="u1@test.com")

    async def test_anonymous_user_fails_to_connect(self):
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        with self.assertRaises(KeyError):
            await communicator.connect()

        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator.scope["user"] = AnonymousUser()
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

        await communicator.disconnect()

    async def test_authorized_user_connects_successfully(self):
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator.scope["user"] = self.user
        self.assertTrue(communicator.scope["user"].is_authenticated)

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.disconnect()

    async def test_client_receives_message_for_his_group(self):
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator.scope["user"] = self.user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_nothing()
        self.assertEqual(response, True)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            self.user.username,
            {
                "type": "send_notification",
                "id": 1,
                "title": "abc",
                "message": "msg",
                "link": "google.com",
                "timestamp": "1",
            },
        )

        response = await communicator.receive_nothing()
        self.assertEqual(response, False)

        response = await communicator.receive_json_from()
        self.assertEqual(
            response,
            {"id": 1, "title": "abc", "text": "msg", "link": "google.com", "timestamp": "1"},
        )
        await communicator.disconnect()

    async def test_client_does_not_receive_message_for_not_his_group(self):
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator.scope["user"] = self.user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_nothing()
        self.assertEqual(response, True)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "different-user",
            {
                "type": "send_notification",
                "id": 1,
                "title": "abc",
                "message": "msg",
                "link": "google.com",
                "timestamp": "1",
            },
        )

        response = await communicator.receive_nothing()
        self.assertEqual(response, True)

        with self.assertRaises(TimeoutError):
            await communicator.receive_json_from()

        await communicator.disconnect()

    async def test_all_clients_with_same_user_receive_message(self):
        communicator1 = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator1.scope["user"] = self.user
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)

        communicator2 = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "GET", "notifications"
        )
        communicator2.scope["user"] = self.user
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected2)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            self.user.username,
            {
                "type": "send_notification",
                "id": 1,
                "title": "abc",
                "message": "msg",
                "link": "google.com",
                "timestamp": "1",
            },
        )

        response1 = await communicator1.receive_json_from()
        response2 = await communicator2.receive_json_from()

        self.assertEqual(
            response1,
            {"id": 1, "title": "abc", "text": "msg", "link": "google.com", "timestamp": "1"},
        )
        self.assertEqual(
            response2,
            {"id": 1, "title": "abc", "text": "msg", "link": "google.com", "timestamp": "1"},
        )

        await communicator1.disconnect()
        await communicator2.disconnect()
