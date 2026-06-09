import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import AsyncMock, Mock, patch

from django.test import SimpleTestCase, override_settings

from notifications.services import delivery_ws


@dataclass
class FakeNotification:
    id: int
    recipient_id: int
    title: str
    body: str
    payload: dict
    created_at: datetime
    last_event_at: datetime


@override_settings(
    NOTIFICATIONS_WS_DETAILED_NOTIFICATION_COOLDOWN_SECONDS=1,
    NOTIFICATIONS_WS_DIGEST_HINT_COOLDOWN_SECONDS=1,
    NOTIFICATIONS_WS_GROUP_SEND_TIMEOUT_SECONDS=1,
)
class TestSendWSNotification(SimpleTestCase):
    def setUp(self) -> None:
        self.layer = Mock()
        self.layer.group_send = AsyncMock()

        created_at = datetime.now(dt_timezone.utc)
        last_event_at = created_at + timedelta(minutes=5)

        self.notification = FakeNotification(
            id=1,
            recipient_id=1,
            title="T",
            body="B",
            payload={"link": "/x/"},
            created_at=created_at,
            last_event_at=last_event_at,
        )

    async def test_returns_when_no_channel_layer(self) -> None:
        with (
            patch.object(delivery_ws, "get_channel_layer", return_value=None),
            patch.object(delivery_ws.Notification.objects, "only") as only_mock,
        ):
            await delivery_ws.send_ws_notification(notification_id=1)
            only_mock.assert_not_called()

    async def test_returns_when_notification_missing(self) -> None:
        # Building a stub chain: Notification.objects.only(...).aget(...)
        only_qs = Mock()
        only_qs.aget = AsyncMock(side_effect=delivery_ws.Notification.DoesNotExist)

        with (
            patch.object(delivery_ws, "get_channel_layer", return_value=self.layer),
            patch.object(
                delivery_ws.Notification.objects, "only", return_value=only_qs
            ),
        ):
            await delivery_ws.send_ws_notification(notification_id=999)

        self.layer.group_send.assert_not_awaited()

    async def test_logs_and_returns_on_unexpected_load_error(
        self,
    ) -> None:
        only_qs = Mock()
        only_qs.aget = AsyncMock(side_effect=RuntimeError("error"))

        with (
            patch.object(delivery_ws, "get_channel_layer", return_value=self.layer),
            patch.object(
                delivery_ws.Notification.objects, "only", return_value=only_qs
            ),
            patch.object(delivery_ws.logger, "exception") as log_exc,
        ):
            await delivery_ws.send_ws_notification(notification_id=1)

        self.layer.group_send.assert_not_awaited()
        log_exc.assert_called_once()

    async def test_sends_detailed_when_throttle_allows(
        self,
    ) -> None:
        only_qs = Mock()
        only_qs.aget = AsyncMock(return_value=self.notification)

        with (
            patch.object(delivery_ws, "get_channel_layer", return_value=self.layer),
            patch.object(
                delivery_ws.Notification.objects, "only", return_value=only_qs
            ),
            patch.object(delivery_ws, "get_personal_group_name", return_value="user_1"),
            patch.object(delivery_ws.cache, "add", return_value=True) as add_mock,
        ):
            await delivery_ws.send_ws_notification(
                notification_id=1, is_new_unread=False
            )

            delivery_ws.Notification.objects.only.assert_called_once_with(
                "id",
                "recipient_id",
                "title",
                "body",
                "payload",
                "created_at",
                "last_event_at",
            )

        self.layer.group_send.assert_awaited_once()
        group, payload = self.layer.group_send.await_args.args
        self.assertEqual(group, "user_1")
        self.assertEqual(payload["type"], "send.notification")
        self.assertEqual(payload["id"], 1)
        self.assertEqual(payload["title"], "T")
        self.assertEqual(payload["body"], "B")
        self.assertEqual(payload["payload"], {"link": "/x/"})
        self.assertFalse(payload["is_new_unread"])
        self.assertIn("timestamp", payload)
        self.assertIn("last_event_at", payload)
        self.assertEqual(payload["timestamp"], self.notification.created_at.isoformat())
        self.assertEqual(
            payload["last_event_at"], self.notification.last_event_at.isoformat()
        )

        add_mock.assert_called_once()
        called_key = add_mock.call_args.args[0]
        self.assertEqual(called_key, "ws_detailed_notification:v1:1")

    async def test_sends_digest_when_detailed_throttled_and_digest_allowed(
        self,
    ) -> None:
        only_qs = Mock()
        only_qs.aget = AsyncMock(return_value=self.notification)

        with (
            patch.object(delivery_ws, "get_channel_layer", return_value=self.layer),
            patch.object(
                delivery_ws.Notification.objects, "only", return_value=only_qs
            ),
            patch.object(delivery_ws, "get_personal_group_name", return_value="user_1"),
            patch.object(
                delivery_ws.cache,
                "add",
                side_effect=[False, True],
            ),
        ):
            await delivery_ws.send_ws_notification(notification_id=1)

        self.layer.group_send.assert_awaited_once()
        group, payload = self.layer.group_send.await_args.args
        self.assertEqual(group, "user_1")
        self.assertEqual(payload, {"type": "send.notification.digest"})

    async def test_cache_error_fails_open_and_logs_warning(self) -> None:
        only_qs = Mock()
        only_qs.aget = AsyncMock(return_value=self.notification)

        with (
            patch.object(delivery_ws, "get_channel_layer", return_value=self.layer),
            patch.object(
                delivery_ws.Notification.objects, "only", return_value=only_qs
            ),
            patch.object(delivery_ws, "get_personal_group_name", return_value="user_1"),
            patch.object(
                delivery_ws.cache, "add", side_effect=RuntimeError("redis down")
            ),
            patch.object(delivery_ws.logger, "warning") as log_warn,
        ):
            await delivery_ws.send_ws_notification(notification_id=1)

        self.layer.group_send.assert_awaited_once()
        args = self.layer.group_send.await_args.args

        self.assertEqual(args[0], "user_1")
        self.assertEqual(args[1]["type"], "send.notification")
        self.assertEqual(args[1]["id"], self.notification.id)

        log_warn.assert_called_once()
        self.assertIn(
            "WS cache throttle failed; allowing send", log_warn.call_args.args[0]
        )


class TestGroupSendWithTimeout(SimpleTestCase):
    def setUp(self) -> None:
        self.layer = Mock()
        self.layer.group_send = AsyncMock()

        now = datetime.now(dt_timezone.utc)
        self.notification = FakeNotification(
            id=1,
            recipient_id=1,
            title="T",
            body="B",
            payload={"link": "/x/"},
            created_at=now,
            last_event_at=now,
        )

    async def test_logs_warning(self) -> None:
        only_qs = Mock()
        only_qs.aget = AsyncMock(return_value=self.notification)

        self.layer.group_send = AsyncMock(side_effect=asyncio.TimeoutError())

        with (
            patch.object(delivery_ws, "get_channel_layer", return_value=self.layer),
            patch.object(
                delivery_ws.Notification.objects, "only", return_value=only_qs
            ),
            patch.object(delivery_ws, "get_personal_group_name", return_value="user_1"),
            patch.object(delivery_ws.cache, "add", return_value=True),
            patch.object(delivery_ws.logger, "warning") as log_warn,
        ):
            await delivery_ws.send_ws_notification(notification_id=1)

        self.layer.group_send.assert_awaited_once()
        log_warn.assert_called_once()
