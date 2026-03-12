from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings

from notifications.consumers import NotificationConsumer
from notifications.models import Notification, NotificationType
from notifications.services.delivery_ws import send_ws_notification
from users.models import User


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    DETAILED_NOTIFICATION_COOLDOWN_SECONDS=0,
    DIGEST_HINT_COOLDOWN_SECONDS=0,
    GROUP_SEND_TIMEOUT_SECONDS=1,
)
class TestWSDeliverySmoke(TransactionTestCase):
    async def test_send_ws_notification_delivers_to_connected_consumer(self):
        user = await sync_to_async(User.objects.create_user)(
            username="u1", email="u1@test.com"
        )
        n = await sync_to_async(Notification.objects.create)(
            recipient=user,
            notification_type=NotificationType.SYSTEM,
            title="T",
            body="B",
            payload={"link": "/x/"},
        )

        comm = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        comm.scope["user"] = user

        connected, _ = await comm.connect()
        self.assertTrue(connected)

        try:
            await send_ws_notification(n.id)

            msg = await comm.receive_json_from(timeout=1)
            self.assertEqual(msg["kind"], "notification")
            self.assertEqual(msg["id"], n.id)
            self.assertEqual(msg["title"], "T")
            self.assertEqual(msg["body"], "B")
            self.assertEqual(msg["payload"], {"link": "/x/"})
            self.assertIn("timestamp", msg)
        finally:
            await comm.disconnect()
