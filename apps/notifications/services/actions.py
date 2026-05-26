from django.db import transaction
from django.db.models import F
from django.utils import timezone

from users.models import User

from ..models import Notification


@transaction.atomic
def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    n = (
        Notification.objects.select_for_update()
        .filter(id=notification_id, recipient_id=user_id)
        .only("id", "read_at")
        .first()
    )
    if not n or n.read_at is not None:
        return False

    n.read_at = timezone.now()
    n.save(update_fields=["read_at"])
    _decrement_unread(user_id)
    return True


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
