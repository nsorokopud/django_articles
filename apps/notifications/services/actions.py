from django.db import transaction
from django.db.models import F
from django.utils import timezone

from users.models import User

from ..models import Notification


@transaction.atomic
def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    updated = Notification.objects.filter(
        id=notification_id,
        recipient_id=user_id,
        read_at__isnull=True,
    ).update(read_at=timezone.now())

    if updated == 1:
        _decrement_unread(user_id)
        return True

    return False


@transaction.atomic
def delete_notification(notification_id: int, user_id: int) -> bool:
    n = (
        Notification.objects.select_for_update()
        .filter(id=notification_id, recipient_id=user_id)
        .values("id", "read_at")
        .first()
    )
    if not n:
        return False

    Notification.objects.filter(id=n["id"]).delete()

    if n["read_at"] is None:
        _decrement_unread(user_id)

    return True


def _decrement_unread(user_id: int) -> None:
    User.objects.filter(id=user_id, unread_notifications_count__gt=0).update(
        unread_notifications_count=F("unread_notifications_count") - 1
    )
