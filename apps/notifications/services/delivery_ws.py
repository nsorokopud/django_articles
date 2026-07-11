import asyncio
import logging
from typing import Any, Optional

from channels.layers import BaseChannelLayer, get_channel_layer
from django.conf import settings
from django.core.cache import cache

from notifications.consumers import get_personal_group_name

from ..models import Notification


logger = logging.getLogger(__name__)


async def send_ws_notification(
    notification_id: int, *, is_new_unread: bool = True
) -> None:
    layer = get_channel_layer()
    if layer is None:
        return

    try:
        n = await Notification.objects.only(
            "id",
            "recipient_id",
            "title",
            "body",
            "payload",
            "created_at",
            "last_event_at",
        ).aget(id=notification_id)
    except Notification.DoesNotExist:
        return
    except Exception:  # pylint: disable=W0718
        logger.exception("WS: failed to load notification id=%s", notification_id)
        return

    await _send_notification_throttled(layer, n, is_new_unread=is_new_unread)


async def _send_notification_throttled(
    layer: BaseChannelLayer, n: Notification, is_new_unread: bool = True
) -> None:
    recipient_id = n.recipient_id
    group = get_personal_group_name(recipient_id)

    detailed_key = f"ws_detailed_notification:v1:{recipient_id}"
    digest_key = f"ws_digest_hint:v1:{recipient_id}"

    detailed_msg = {
        "type": "send.notification",
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "payload": n.payload,
        "timestamp": n.created_at.isoformat(),
        "last_event_at": n.last_event_at.isoformat(),
        "is_new_unread": is_new_unread,
    }

    if _throttle_allows_send(
        detailed_key,
        settings.NOTIFICATIONS_WS_DETAILED_NOTIFICATION_COOLDOWN_SECONDS,
        recipient_id=recipient_id,
    ):
        await _group_send_with_timeout(
            layer,
            group,
            detailed_msg,
            log_prefix="WS detailed send",
            notification_id=n.id,
            recipient_id=recipient_id,
        )
        return

    if _throttle_allows_send(
        digest_key,
        settings.NOTIFICATIONS_WS_DIGEST_HINT_COOLDOWN_SECONDS,
        recipient_id=recipient_id,
    ):
        await _group_send_with_timeout(
            layer,
            group,
            {"type": "send.notification.digest"},
            log_prefix="WS digest send",
            recipient_id=recipient_id,
        )


def _throttle_allows_send(
    key: str, cooldown_seconds: int, *, recipient_id: int
) -> bool:
    try:
        return cache.add(key, True, timeout=cooldown_seconds)
    except Exception:  # pylint: disable=W0718
        logger.warning(
            "WS cache throttle failed; allowing send (recipient_id=%s key=%s)",
            recipient_id,
            key,
            exc_info=True,
        )
        return True


async def _group_send_with_timeout(
    layer: BaseChannelLayer,
    group: str,
    payload: dict[str, Any],
    *,
    log_prefix: str,
    notification_id: Optional[int] = None,
    recipient_id: Optional[int] = None,
) -> None:
    context = []
    if notification_id is not None:
        context.append(f"notification_id={notification_id}")
    if recipient_id is not None:
        context.append(f"recipient_id={recipient_id}")

    log_suffix = f" ({', '.join(context)})" if context else ""

    try:
        async with asyncio.timeout(
            settings.NOTIFICATIONS_WS_GROUP_SEND_TIMEOUT_SECONDS
        ):
            await layer.group_send(group, payload)
    except asyncio.CancelledError:  # pylint: disable=W0706
        raise
    except (asyncio.TimeoutError, OSError):
        logger.warning("%s infra error%s", log_prefix, log_suffix, exc_info=True)
    except Exception:  # pylint: disable=W0718
        logger.exception("%s unexpected error%s", log_prefix, log_suffix)
