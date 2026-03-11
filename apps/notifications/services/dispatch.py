from dataclasses import dataclass

from django.db import transaction

from notifications.models import NotificationType

from ..tasks import send_notification_email_task, send_notification_ws_task


@dataclass(frozen=True)
class DeliveryPlan:
    ws: bool = True
    email: bool = False


def get_delivery_plan(*, notification_type: str) -> DeliveryPlan:
    if notification_type == NotificationType.SYSTEM:
        return DeliveryPlan(ws=True, email=True)
    return DeliveryPlan(ws=True, email=False)


def dispatch_notification_after_commit(
    *,
    notification_id: int,
    notification_type: str,
    is_new_unread: bool = True,
) -> None:
    plan = get_delivery_plan(notification_type=notification_type)

    if plan.ws:
        transaction.on_commit(
            lambda: send_notification_ws_task.delay(notification_id, is_new_unread)
        )

    if plan.email:
        transaction.on_commit(
            lambda: send_notification_email_task.delay(notification_id)
        )
