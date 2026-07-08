import asyncio
import logging
from typing import Any, Literal, Optional, TypedDict

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from users.models import User


logger = logging.getLogger(__name__)

WS_CLOSE_POLICY_VIOLATION = 1008
WS_CLOSE_INTERNAL_ERROR = 1011


def get_personal_group_name(user_id: int) -> str:
    return f"user_{user_id}"


class NotificationEvent(TypedDict):
    type: Literal["send.notification"]
    id: int
    title: str
    body: str
    payload: Optional[dict[str, Any]]
    timestamp: str
    last_event_at: str
    is_new_unread: bool


class DigestHintEvent(TypedDict):
    type: Literal["send.notification.digest"]


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Push-only WS consumer for real-time notifications.

    Delivery is best-effort: individual notification messages may be dropped when
    a previous send is still in progress (to avoid buffering/backpressure). When drops
    occur, a single "digest" message is sent to hint the client to refetch the inbox
    from the DB.
    """

    personal_group: str
    _send_lock: asyncio.Lock
    _is_closing: bool
    _digest_pending: bool

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._send_lock = asyncio.Lock()
        self._is_closing = False
        self._digest_pending = False

    async def connect(self) -> None:
        user = self.scope.get("user")

        error_code = self._validate_connection(user)
        if error_code is not None:
            await self._safe_close(code=error_code)
            return

        # Joining group before accepting to not miss events during the handshake.
        self.personal_group = get_personal_group_name(user.id)
        if not await self._join_group(self.personal_group):
            await self._safe_close(code=WS_CLOSE_INTERNAL_ERROR)
            return

        if not await self._accept_with_timeout():
            await self._leave_group(self.personal_group)
            return

    async def disconnect(self, code: int) -> None:
        self._digest_pending = False
        self._is_closing = True

        if getattr(self, "personal_group", None):
            await self._leave_group(self.personal_group)

        await super().disconnect(code)

    async def receive_json(self, content: Any, **kwargs) -> None:
        """Client messages are not supported; any message from client closes (1008)."""
        if self._is_closing:
            return

        await self._safe_close(code=WS_CLOSE_POLICY_VIOLATION)

    async def send_notification(self, event: NotificationEvent) -> None:
        msg = self._build_message_from_event(event)
        if msg is None or self._is_closing:
            return

        # If already sending, don't queue more; just ensure a digest hint is sent later.
        if self._send_lock.locked():
            self._digest_pending = True
            return

        await self._send_payload_locked(
            msg, log_prefix=f"Notification send (id={msg.get('id', -1)})"
        )

    async def send_notification_digest(self, _event: DigestHintEvent) -> None:
        if self._is_closing:
            return

        if self._send_lock.locked():
            self._digest_pending = True
            return

        await self._send_payload_locked(
            {"kind": "digest"}, log_prefix="Notification digest send"
        )

    def _validate_connection(self, user: Optional[User]) -> Optional[int]:
        if not self.channel_layer:
            logger.error("No channel layer configured.")
            return WS_CLOSE_INTERNAL_ERROR

        if user is None or not getattr(user, "is_authenticated", False):
            logger.debug("Rejected unauthenticated websocket connection.")
            return WS_CLOSE_POLICY_VIOLATION

        return None

    async def _join_group(self, group_name: str) -> bool:
        try:
            async with asyncio.timeout(
                settings.NOTIFICATIONS_WS_GROUP_OPERATION_TIMEOUT_SECONDS
            ):
                await self.channel_layer.group_add(group_name, self.channel_name)
            return True
        except (asyncio.TimeoutError, ConnectionError, OSError):
            logger.error("group_add failed: %s", group_name, exc_info=True)
            return False

    async def _leave_group(self, group_name: str) -> None:
        try:
            async with asyncio.timeout(
                settings.NOTIFICATIONS_WS_GROUP_OPERATION_TIMEOUT_SECONDS
            ):
                await self.channel_layer.group_discard(group_name, self.channel_name)
        except (asyncio.TimeoutError, ConnectionError, OSError):
            logger.debug("group_discard failed: %s", group_name, exc_info=True)

    async def _accept_with_timeout(self) -> bool:
        try:
            async with asyncio.timeout(
                settings.NOTIFICATIONS_WS_ACCEPT_TIMEOUT_SECONDS
            ):
                await self.accept()
                return True
        except asyncio.TimeoutError:
            logger.error("Connection accept timed out.")
            await self._safe_close(code=WS_CLOSE_INTERNAL_ERROR)
            return False

    async def _safe_close(self, code: int) -> None:
        self._digest_pending = False

        if self._is_closing:
            return
        self._is_closing = True
        try:
            await self.close(code=code)
        except Exception:  # pylint: disable=W0718
            logger.debug("WS close failed", exc_info=True)

    async def _send_payload_locked(
        self, payload: dict[str, Any], *, log_prefix: str
    ) -> bool:
        if self._is_closing:
            return False

        async with self._send_lock:
            ok = await self._send_json_with_timeout(payload, log_prefix=log_prefix)
            if not ok or self._is_closing:
                return False

            kind = payload.get("kind")

            if kind == "digest":
                self._digest_pending = False
                return True

            # If notifications were dropped while a previous send was in progress,
            # emit one digest after the notification.
            if kind == "notification" and self._digest_pending:
                ok2 = await self._send_json_with_timeout(
                    {"kind": "digest"}, log_prefix="Notification digest send"
                )
                if ok2:
                    self._digest_pending = False

            return True

    async def _send_json_with_timeout(
        self, payload: dict[str, Any], *, log_prefix: str = "WS send"
    ) -> bool:
        if self._is_closing:
            return False

        try:
            async with asyncio.timeout(
                settings.NOTIFICATIONS_WS_SEND_JSON_TIMEOUT_SECONDS
            ):
                await self.send_json(payload)
            return True

        except asyncio.CancelledError:  # pylint: disable=W0706
            raise

        except (asyncio.TimeoutError, OSError, RuntimeError) as e:
            logger.warning("%s failed: %s", log_prefix, e)
            await self._safe_close(code=WS_CLOSE_INTERNAL_ERROR)
            return False

        except Exception:  # pylint: disable=W0718
            logger.exception("%s failed unexpectedly", log_prefix)
            await self._safe_close(code=WS_CLOSE_INTERNAL_ERROR)
            return False

    @staticmethod
    def _build_message_from_event(event: NotificationEvent) -> Optional[dict[str, Any]]:
        try:
            return {
                "kind": "notification",
                "id": event["id"],
                "title": event["title"],
                "body": event["body"],
                "payload": event.get("payload"),
                "timestamp": event["timestamp"],
                "last_event_at": event["last_event_at"],
                "is_new_unread": bool(event.get("is_new_unread", True)),
            }
        except KeyError as e:
            logger.warning(
                "Invalid notification event payload (id=%s): missing %s",
                event.get("id"),
                e,
            )
            return None
