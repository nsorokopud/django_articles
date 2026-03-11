import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Optional
from unittest import mock

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from notifications.consumers import (
    WS_CLOSE_INTERNAL_ERROR,
    WS_CLOSE_POLICY_VIOLATION,
    NotificationConsumer,
    get_personal_group_name,
)


class UserStub:
    def __init__(self, user_id: int = 1, authenticated: bool = True):
        self.id = user_id
        self.is_authenticated = authenticated


class TestNotificationConsumerUnit(SimpleTestCase):
    def test_validate_prereqs_unauthenticated_returns_1008(self):
        consumer = NotificationConsumer()
        consumer.channel_layer = object()

        code = consumer._validate_connection(UserStub(authenticated=False))
        self.assertEqual(code, WS_CLOSE_POLICY_VIOLATION)

    def test_validate_prereqs_no_channel_layer_returns_1011(self):
        consumer = NotificationConsumer()
        consumer.channel_layer = None

        code = consumer._validate_connection(UserStub(authenticated=True))
        self.assertEqual(code, WS_CLOSE_INTERNAL_ERROR)

    def test_validate_prereqs_ok_returns_none(self):
        consumer = NotificationConsumer()
        consumer.channel_layer = object()

        code = consumer._validate_connection(UserStub(authenticated=True))
        self.assertIsNone(code)

    def test_build_message_from_event_missing_keys_returns_none(self):
        event = {"type": "send.notification", "id": 1, "title": "x"}
        msg = NotificationConsumer._build_message_from_event(event)
        self.assertIsNone(msg)

    def test_build_message_from_event_includes_payload_none(self):
        event = {
            "type": "send.notification",
            "id": 1,
            "title": "t",
            "body": "b",
            "payload": None,
            "timestamp": "2026-01-01T12:00:00Z",
        }
        msg = NotificationConsumer._build_message_from_event(event)
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("payload", msg)
        self.assertIsNone(msg["payload"])

    def test_build_message_from_event_defaults_payload_to_none(self):
        event = {
            "type": "send.notification",
            "id": 2,
            "title": "t",
            "body": "b",
            "timestamp": "2026-01-01T12:00:00Z",
        }
        msg = NotificationConsumer._build_message_from_event(event)
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("payload", msg)
        self.assertIsNone(msg["payload"])

    def test_build_message_from_event_includes_is_new_unread(self):
        event = {
            "type": "send.notification",
            "id": 1,
            "title": "t",
            "body": "b",
            "payload": None,
            "timestamp": "2026-01-01T12:00:00Z",
            "is_new_unread": False,
        }
        msg = NotificationConsumer._build_message_from_event(event)
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("is_new_unread", msg)
        self.assertFalse(msg["is_new_unread"])

    def test_build_message_from_event_defaults_is_new_unread_to_true(self):
        event = {
            "type": "send.notification",
            "id": 1,
            "title": "t",
            "body": "b",
            "payload": None,
            "timestamp": "2026-01-01T12:00:00Z",
        }
        msg = NotificationConsumer._build_message_from_event(event)
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("is_new_unread", msg)
        self.assertTrue(msg["is_new_unread"])

    async def test_safe_close_is_idempotent(self):
        consumer = NotificationConsumer()
        consumer.close = mock.AsyncMock()

        await consumer._safe_close(code=WS_CLOSE_INTERNAL_ERROR)
        await consumer._safe_close(code=WS_CLOSE_INTERNAL_ERROR)

        self.assertEqual(consumer.close.await_count, 1)


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    ACCEPT_TIMEOUT_SECONDS=0.2,
    GROUP_OPERATION_TIMEOUT_SECONDS=0.2,
    SEND_JSON_TIMEOUT_SECONDS=0.2,
)
class TestNotificationConsumerASGI(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.no_message_timeout = (
            max(
                settings.ACCEPT_TIMEOUT_SECONDS,
                settings.GROUP_OPERATION_TIMEOUT_SECONDS,
                settings.SEND_JSON_TIMEOUT_SECONDS,
            )
            + 0.2  # > timeouts for CI jitter
        )

    def tearDown(self) -> None:
        layer = get_channel_layer()

        for attr in ("groups", "channels"):
            val = getattr(layer, attr, None)
            if isinstance(val, dict):
                val.clear()

        super().tearDown()

    @staticmethod
    def _notification_event(
        notif_id: int,
        *,
        title: str = "t",
        body: str = "b",
        payload=None,
        timestamp: str = "2026-01-01T12:00:00Z",
        is_new_unread: bool = True,
    ) -> dict:
        return {
            "type": "send.notification",
            "id": notif_id,
            "title": title,
            "body": body,
            "payload": payload,
            "timestamp": timestamp,
            "is_new_unread": is_new_unread,
        }

    @staticmethod
    def _digest_event() -> dict:
        return {"type": "send.notification.digest"}

    def _make_communicator(self, user: UserStub) -> WebsocketCommunicator:
        application = NotificationConsumer.as_asgi()
        comm = WebsocketCommunicator(application, "/ws/notifications/")
        comm.scope["user"] = user
        return comm

    def _make_communicator_with_instance(self, user: UserStub):
        """- Captures the consumer instance in `captured["consumer"]`;
        - Exposes `captured["consumer_ready"]` (Event) set when the consumer
            instance is constructed (for handshake-time tests);
        - Exposes `_test_send_notification_finished` (Event) for deterministic
            synchronization in send_notification tests.
        """
        captured: dict[str, object] = {}
        captured["consumer_ready"] = asyncio.Event()

        class TestConsumer(NotificationConsumer):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                captured["consumer"] = self
                captured["consumer_ready"].set()
                self._test_send_notification_finished = asyncio.Event()

            async def send_notification(self, event):
                try:
                    return await super().send_notification(event)
                finally:
                    self._test_send_notification_finished.set()

        application = TestConsumer.as_asgi()
        comm = WebsocketCommunicator(application, "/ws/notifications/")
        comm.scope["user"] = user
        return comm, captured

    async def _disconnect_safely(self, comm: WebsocketCommunicator):
        # If the app task crashed, asgiref may re-raise on disconnect().
        with suppress(Exception):
            await comm.disconnect()

    @asynccontextmanager
    async def _connected_comm(self, comm: WebsocketCommunicator):
        """Ensures communicator always gets disconnected."""
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        try:
            yield comm
        finally:
            await self._disconnect_safely(comm)

    def _assert_handshake_rejected(
        self,
        connected: bool,
        close_code: Optional[int],
        expected_code: int,
    ) -> None:
        self.assertFalse(connected)
        # ASGI server/version differences: handshake close_code may be None.
        self.assertIn(close_code, (expected_code, None))

    async def _assert_closed_with_code(
        self, comm: WebsocketCommunicator, code: int, timeout: float = 1.0
    ):
        """Robust for closes that happen AFTER a successful connect():
        close may arrive after other output; keep reading until websocket.close.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                self.fail(
                    f"Timed out waiting for websocket.close (expected code={code})."
                )

            event = await comm.receive_output(timeout=remaining)
            if event["type"] == "websocket.close":
                self.assertEqual(event.get("code"), code)
                return

    async def test_rejects_unauthenticated_user(self):
        comm = self._make_communicator(UserStub(authenticated=False))
        try:
            connected, close_code = await comm.connect()
            self._assert_handshake_rejected(
                connected, close_code, WS_CLOSE_POLICY_VIOLATION
            )
        finally:
            await self._disconnect_safely(comm)

    async def test_accepts_authenticated_user(self):
        comm = self._make_communicator(UserStub())
        async with self._connected_comm(comm):
            pass

    async def test_receive_json_closes_with_1008(self):
        comm = self._make_communicator(UserStub(user_id=1, authenticated=True))
        async with self._connected_comm(comm):
            await comm.send_json_to({"type": "abc"})
            await self._assert_closed_with_code(
                comm, WS_CLOSE_POLICY_VIOLATION, timeout=1.0
            )

    async def test_group_send_delivers_notification(self):
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)

        async with self._connected_comm(comm):
            layer = get_channel_layer()
            await layer.group_send(
                get_personal_group_name(user.id), self._notification_event(1)
            )

            msg = await comm.receive_json_from(timeout=1)
            self.assertEqual(msg["kind"], "notification")
            self.assertEqual(msg["id"], 1)
            self.assertEqual(msg["title"], "t")
            self.assertEqual(msg["body"], "b")
            self.assertIsNone(msg["payload"])
            self.assertEqual(msg["timestamp"], "2026-01-01T12:00:00Z")
            self.assertTrue(msg["is_new_unread"])

    async def test_group_send_delivers_notification_with_is_new_unread_false(self):
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)

        async with self._connected_comm(comm):
            layer = get_channel_layer()
            await layer.group_send(
                get_personal_group_name(user.id),
                self._notification_event(1, is_new_unread=False),
            )

            msg = await comm.receive_json_from(timeout=1)
            self.assertEqual(msg["kind"], "notification")
            self.assertEqual(msg["id"], 1)
            self.assertFalse(msg["is_new_unread"])

    async def test_digest_event_delivers_digest_message_when_idle(self):
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)

        async with self._connected_comm(comm):
            layer = get_channel_layer()
            await layer.group_send(
                get_personal_group_name(user.id), self._digest_event()
            )

            msg = await comm.receive_json_from(timeout=1)
            self.assertEqual(msg["kind"], "digest")

    async def test_invalid_notification_event_is_ignored(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            with mock.patch.object(
                consumer, "send_json", new=mock.AsyncMock()
            ) as send_mock:
                layer = get_channel_layer()
                await layer.group_send(
                    get_personal_group_name(user.id),
                    {"type": "send.notification", "id": 1, "title": "x"},
                )

                await asyncio.wait_for(
                    consumer._test_send_notification_finished.wait(), timeout=1.0
                )
                send_mock.assert_not_awaited()

            with self.assertRaises(asyncio.TimeoutError):
                await comm.receive_json_from(timeout=self.no_message_timeout)

    async def test_two_connections_same_user_receive_group_message(self):
        user = UserStub(user_id=1, authenticated=True)
        comm1 = self._make_communicator(user)
        comm2 = self._make_communicator(user)

        async with self._connected_comm(comm1), self._connected_comm(comm2):
            layer = get_channel_layer()
            await layer.group_send(
                get_personal_group_name(user.id), self._notification_event(1)
            )

            m1 = await comm1.receive_json_from(timeout=1)
            m2 = await comm2.receive_json_from(timeout=1)

            self.assertEqual(m1["kind"], "notification")
            self.assertEqual(m2["kind"], "notification")
            self.assertEqual(m1["id"], 1)
            self.assertEqual(m2["id"], 1)
            self.assertTrue(m1["is_new_unread"])
            self.assertTrue(m2["is_new_unread"])

    async def test_group_send_does_not_leak_across_users(self):
        user_a = UserStub(user_id=1, authenticated=True)
        user_b = UserStub(user_id=2, authenticated=True)

        comm_a = self._make_communicator(user_a)
        comm_b = self._make_communicator(user_b)

        async with self._connected_comm(comm_a), self._connected_comm(comm_b):
            layer = get_channel_layer()
            await layer.group_send(
                get_personal_group_name(user_b.id),
                self._notification_event(2, title="toB"),
            )

            msg_b = await comm_b.receive_json_from(timeout=1)
            self.assertEqual(msg_b["kind"], "notification")
            self.assertEqual(msg_b["title"], "toB")

            with self.assertRaises(asyncio.TimeoutError):
                await comm_a.receive_json_from(timeout=self.no_message_timeout)

    async def test_join_group_false_rejects_connection(self):
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)

        try:
            with mock.patch.object(
                NotificationConsumer,
                "_join_group",
                new=mock.AsyncMock(return_value=False),
            ):
                connected, close_code = await comm.connect()
                self._assert_handshake_rejected(
                    connected, close_code, WS_CLOSE_INTERNAL_ERROR
                )
        finally:
            await self._disconnect_safely(comm)

    async def test_join_group_exception_rejects_connection(self):
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)

        layer = get_channel_layer()

        async def raising_group_add(group: str, channel: str):
            raise ConnectionError("error")

        try:
            with mock.patch.object(layer, "group_add", new=raising_group_add):
                connected, close_code = await comm.connect()
                self._assert_handshake_rejected(
                    connected, close_code, WS_CLOSE_INTERNAL_ERROR
                )
        finally:
            await self._disconnect_safely(comm)

    async def test_join_group_timeout_rejects_connection(self):
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)

        layer = get_channel_layer()

        async def slow_group_add(group: str, channel: str):
            await asyncio.sleep(settings.GROUP_OPERATION_TIMEOUT_SECONDS + 0.5)

        try:
            with mock.patch.object(layer, "group_add", new=slow_group_add):
                connected, close_code = await comm.connect()
                self._assert_handshake_rejected(
                    connected, close_code, WS_CLOSE_INTERNAL_ERROR
                )
        finally:
            await self._disconnect_safely(comm)

    async def test_accept_timeout_closes_with_1011(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)
        connect_task = None

        async def slow_accept(_self, *args, **kwargs):
            await asyncio.sleep(settings.ACCEPT_TIMEOUT_SECONDS + 0.5)

        try:
            with mock.patch.object(NotificationConsumer, "accept", new=slow_accept):
                connect_task = asyncio.create_task(comm.connect())

                await asyncio.wait_for(captured["consumer_ready"].wait(), timeout=1.0)
                consumer = captured["consumer"]
                assert isinstance(consumer, NotificationConsumer)

                connected, close_code = await connect_task
                self._assert_handshake_rejected(
                    connected, close_code, WS_CLOSE_INTERNAL_ERROR
                )
                self.assertTrue(getattr(consumer, "_is_closing", False))
        finally:
            if connect_task is not None and not connect_task.done():
                connect_task.cancel()
                with suppress(asyncio.CancelledError):
                    await connect_task
            await self._disconnect_safely(comm)

    async def test_send_timeout_closes_socket_with_1011_for_notification(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async def slow_send_json(content, close=False, **kwargs):
            await asyncio.sleep(settings.SEND_JSON_TIMEOUT_SECONDS + 0.5)

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            with mock.patch.object(consumer, "send_json", new=slow_send_json):
                layer = get_channel_layer()
                await layer.group_send(
                    get_personal_group_name(user.id),
                    self._notification_event(1),
                )

                await self._assert_closed_with_code(
                    comm, WS_CLOSE_INTERNAL_ERROR, timeout=2.0
                )

    async def test_send_connection_reset_closes_1011_for_notification(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async def raising_send_json(_content, close=False, **kwargs):
            raise ConnectionResetError("peer reset")

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            with mock.patch.object(consumer, "send_json", new=raising_send_json):
                layer = get_channel_layer()
                await layer.group_send(
                    get_personal_group_name(user.id),
                    self._notification_event(1),
                )

                await self._assert_closed_with_code(
                    comm, WS_CLOSE_INTERNAL_ERROR, timeout=2.0
                )

    async def test_send_runtime_error_closes_1011_for_notification(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async def raising_send_json(_content, close=False, **kwargs):
            raise RuntimeError("error")

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            with mock.patch.object(consumer, "send_json", new=raising_send_json):
                layer = get_channel_layer()
                await layer.group_send(
                    get_personal_group_name(user.id),
                    self._notification_event(1),
                )

                await self._assert_closed_with_code(
                    comm, WS_CLOSE_INTERNAL_ERROR, timeout=2.0
                )

    async def test_digest_send_failure_closes_socket(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            original_send_json = consumer.send_json

            async def fail_digest_only(content, close=False, **kwargs):
                if isinstance(content, dict) and content.get("kind") == "digest":
                    raise ConnectionResetError("digest failed")
                return await original_send_json(content, close=close, **kwargs)

            with mock.patch.object(consumer, "send_json", new=fail_digest_only):
                layer = get_channel_layer()
                await layer.group_send(
                    get_personal_group_name(user.id), self._digest_event()
                )

                await self._assert_closed_with_code(
                    comm, WS_CLOSE_INTERNAL_ERROR, timeout=2.0
                )

    async def test_autodigest_failure_after_overlap_closes_socket(self):
        """Scenario:
        - Block notification #1 so lock is held.
        - Overlap notification #2 => dropped, _digest_pending=True.
        - Release #1 => notification #1 sent, then autodigest attempted.
        - Make autodigest send fail => socket must close (1011).
        - Client receives notification #1, connection closes.
        """
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        first_send_started = asyncio.Event()
        release_first_send = asyncio.Event()

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            original_send_json = consumer.send_json

            async def patched_send_json(content, close=False, **kwargs):
                if (
                    isinstance(content, dict)
                    and content.get("kind") == "notification"
                    and content.get("id") == 1
                ):
                    first_send_started.set()
                    await release_first_send.wait()
                    return await original_send_json(content, close=close, **kwargs)

                if isinstance(content, dict) and content.get("kind") == "digest":
                    raise ConnectionResetError("digest failed")

                return await original_send_json(content, close=close, **kwargs)

            event1 = self._notification_event(
                1, title="A", body="A", payload=None, timestamp="2026-01-01T12:00:00Z"
            )
            event2 = self._notification_event(
                2, title="B", body="B", payload=None, timestamp="2026-01-01T12:00:01Z"
            )

            with mock.patch.object(consumer, "send_json", new=patched_send_json):
                t1 = asyncio.create_task(consumer.send_notification(event1))
                await asyncio.wait_for(first_send_started.wait(), timeout=1.0)

                await consumer.send_notification(event2)
                self.assertTrue(consumer._digest_pending)

                release_first_send.set()
                await t1

                m1 = await comm.receive_json_from(timeout=1)
                self.assertEqual(m1["kind"], "notification")
                self.assertEqual(m1["id"], 1)

                await self._assert_closed_with_code(
                    comm, WS_CLOSE_INTERNAL_ERROR, timeout=2.0
                )

    async def test_one_digest_sent_on_overlapping_notifications(self):
        """Concurrency: overlap notifications => one digest sent."""
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        first_send_started = asyncio.Event()
        release_first_send = asyncio.Event()

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            original_send_json = consumer.send_json

            async def patched_send_json(content, close=False, **kwargs):
                if (
                    isinstance(content, dict)
                    and content.get("kind") == "notification"
                    and content.get("id") == 1
                ):
                    first_send_started.set()
                    await release_first_send.wait()
                return await original_send_json(content, close=close, **kwargs)

            event1 = self._notification_event(
                1, title="A", body="A", payload=None, timestamp="2026-01-01T12:00:00Z"
            )
            event2 = self._notification_event(
                2, title="B", body="B", payload=None, timestamp="2026-01-01T12:00:01Z"
            )

            with mock.patch.object(consumer, "send_json", new=patched_send_json):
                t1 = asyncio.create_task(consumer.send_notification(event1))
                await asyncio.wait_for(first_send_started.wait(), timeout=1.0)

                await consumer.send_notification(event2)
                self.assertTrue(consumer._digest_pending)

                release_first_send.set()
                await t1

                m1 = await comm.receive_json_from(timeout=1)
                self.assertEqual(m1["kind"], "notification")
                self.assertEqual(m1["id"], 1)

                m2 = await comm.receive_json_from(timeout=1)
                self.assertEqual(m2["kind"], "digest")

                with self.assertRaises(asyncio.TimeoutError):
                    await comm.receive_json_from(timeout=self.no_message_timeout)

                self.assertFalse(consumer._digest_pending)

    async def test_multiple_overlaps_emit_single_digest(self):
        """Concurrency: multiple notifications overlap => one digest."""
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        first_send_started = asyncio.Event()
        release_first_send = asyncio.Event()

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            original_send_json = consumer.send_json

            async def patched_send_json(content, close=False, **kwargs):
                if (
                    isinstance(content, dict)
                    and content.get("kind") == "notification"
                    and content.get("id") == 1
                ):
                    first_send_started.set()
                    await release_first_send.wait()
                return await original_send_json(content, close=close, **kwargs)

            with mock.patch.object(consumer, "send_json", new=patched_send_json):
                t1 = asyncio.create_task(
                    consumer.send_notification(
                        self._notification_event(1, title="N1", body="N1")
                    )
                )
                await asyncio.wait_for(first_send_started.wait(), timeout=1.0)

                for n in (2, 3, 4):
                    await consumer.send_notification(
                        self._notification_event(n, title=f"N{n}", body=f"N{n}")
                    )

                self.assertTrue(consumer._digest_pending)

                release_first_send.set()
                await t1

                m1 = await comm.receive_json_from(timeout=1)
                self.assertEqual(m1["kind"], "notification")
                self.assertEqual(m1["id"], 1)

                m2 = await comm.receive_json_from(timeout=1)
                self.assertEqual(m2["kind"], "digest")

                with self.assertRaises(asyncio.TimeoutError):
                    await comm.receive_json_from(timeout=self.no_message_timeout)

    async def test_notification_dropped_when_send_lock_held_by_digest(self):
        """Digest holds lock => notification dropped, digest arrives."""
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        digest_send_started = asyncio.Event()
        release_digest_send = asyncio.Event()

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            original_send_json = consumer.send_json

            async def patched_send_json(content, close=False, **kwargs):
                if isinstance(content, dict) and content.get("kind") == "digest":
                    digest_send_started.set()
                    await release_digest_send.wait()
                return await original_send_json(content, close=close, **kwargs)

            with mock.patch.object(consumer, "send_json", new=patched_send_json):
                digest_task = asyncio.create_task(
                    consumer.send_notification_digest(self._digest_event())
                )
                await asyncio.wait_for(digest_send_started.wait(), timeout=1.0)

                await consumer.send_notification(self._notification_event(1))
                self.assertTrue(consumer._digest_pending)

                release_digest_send.set()
                await digest_task

                msg = await comm.receive_json_from(timeout=1)
                self.assertEqual(msg["kind"], "digest")

                with self.assertRaises(asyncio.TimeoutError):
                    await comm.receive_json_from(timeout=self.no_message_timeout)

                self.assertFalse(consumer._digest_pending)

    async def test_digest_postponed_and_sent_once_during_notification_send(
        self,
    ):
        """Scenario:
        - Start sending notification #1; block its send_json so _send_lock is held.
        - Call the digest handler while lock held => should NOT send digest immediately,
            only set _digest_pending=True.
        - Release notification #1 send => client receives notification #1, then exactly
            one digest.
        - No further messages.
        """
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        notif_send_started = asyncio.Event()
        release_notif_send = asyncio.Event()

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            original_send_json = consumer.send_json

            async def patched_send_json(content, close=False, **kwargs):
                if (
                    isinstance(content, dict)
                    and content.get("kind") == "notification"
                    and content.get("id") == 1
                ):
                    notif_send_started.set()
                    await release_notif_send.wait()
                return await original_send_json(content, close=close, **kwargs)

            event1 = self._notification_event(1, title="A", body="A")
            digest_event = self._digest_event()

            with mock.patch.object(consumer, "send_json", new=patched_send_json):
                t1 = asyncio.create_task(consumer.send_notification(event1))
                await asyncio.wait_for(notif_send_started.wait(), timeout=1.0)

                await consumer.send_notification_digest(digest_event)
                self.assertTrue(consumer._digest_pending)

                release_notif_send.set()
                await t1

                m1 = await comm.receive_json_from(timeout=1.0)
                self.assertEqual(m1["kind"], "notification")
                self.assertEqual(m1["id"], 1)

                m2 = await comm.receive_json_from(timeout=1.0)
                self.assertEqual(m2["kind"], "digest")

                with self.assertRaises(asyncio.TimeoutError):
                    await comm.receive_json_from(timeout=self.no_message_timeout)

                self.assertFalse(consumer._digest_pending)

    async def test_disconnect_removes_channel_from_group_inmemory_layer(self):
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)
        layer = get_channel_layer()
        group = get_personal_group_name(user.id)

        async with self._connected_comm(comm):
            await comm.disconnect()

            await layer.group_send(group, self._notification_event(999))
            with self.assertRaises(asyncio.TimeoutError):
                await comm.receive_json_from(timeout=self.no_message_timeout)

    async def test_disconnect_attempts_group_discard_and_handles_errors(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)
        group = get_personal_group_name(user.id)
        consumer = None
        original_discard = None

        async with self._connected_comm(comm):
            consumer_obj = captured["consumer"]
            assert isinstance(consumer_obj, NotificationConsumer)
            consumer = consumer_obj

            original_discard = consumer.channel_layer.group_discard
            discard_mock = mock.AsyncMock(
                side_effect=ConnectionError("group_discard failed")
            )
            consumer.channel_layer.group_discard = discard_mock

            await comm.disconnect()

            self.assertGreaterEqual(discard_mock.call_count, 1)
            discard_mock.assert_any_call(group, consumer.channel_name)

        if consumer is not None and original_discard is not None:
            consumer.channel_layer.group_discard = original_discard

    async def test_receive_json_is_noop_after_disconnect(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            await comm.disconnect()

            with (
                mock.patch.object(
                    consumer, "send_json", new=mock.AsyncMock()
                ) as send_mock,
                mock.patch.object(
                    consumer, "_safe_close", new=mock.AsyncMock()
                ) as close_mock,
            ):
                await consumer.receive_json({"type": "nope"})
                send_mock.assert_not_awaited()
                close_mock.assert_not_awaited()

    async def test_disconnect_clears_digest_pending_flag(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            consumer._digest_pending = True
            self.assertTrue(consumer._digest_pending)

            await comm.disconnect()

            self.assertFalse(consumer._digest_pending)

    async def test_cancelled_error_is_not_swallowed_by_send_notification(self):
        user = UserStub(user_id=1, authenticated=True)
        comm, captured = self._make_communicator_with_instance(user)

        async with self._connected_comm(comm):
            consumer = captured["consumer"]
            assert isinstance(consumer, NotificationConsumer)

            async def raising_cancelled(_content, close=False, **kwargs):
                raise asyncio.CancelledError()

            event = self._notification_event(1)

            with mock.patch.object(consumer, "send_json", new=raising_cancelled):
                with self.assertRaises(asyncio.CancelledError):
                    await consumer.send_notification(event)

    async def test_mixed_notification_digest_sequence_processed_correctly(self):
        """Notification -> digest -> notification; all messages delivered in order."""
        user = UserStub(user_id=1, authenticated=True)
        comm = self._make_communicator(user)

        async with self._connected_comm(comm):
            layer = get_channel_layer()
            group = get_personal_group_name(user.id)

            await layer.group_send(
                group, self._notification_event(1, title="A", body="A", payload=None)
            )
            await layer.group_send(group, self._digest_event())
            await layer.group_send(
                group,
                self._notification_event(
                    2,
                    title="B",
                    body="B",
                    payload=None,
                    timestamp="2026-01-01T12:00:01Z",
                ),
            )

            m1 = await comm.receive_json_from(timeout=1)
            m2 = await comm.receive_json_from(timeout=1)
            m3 = await comm.receive_json_from(timeout=1)

            self.assertEqual(m1["kind"], "notification")
            self.assertEqual(m1["id"], 1)
            self.assertEqual(m2["kind"], "digest")
            self.assertEqual(m3["kind"], "notification")
            self.assertEqual(m3["id"], 2)
