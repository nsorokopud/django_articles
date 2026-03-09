from django.db.models.query import QuerySet

from users.models import User

from ..models import Notification


def find_notifications_by_user(user_id: int) -> QuerySet[Notification]:
    return Notification.objects.filter(recipient_id=user_id)


def get_unread_notifications_count_by_user(user_id: int) -> int:
    return (
        User.objects.filter(id=user_id)
        .values_list("unread_notifications_count", flat=True)
        .first()
    ) or 0
