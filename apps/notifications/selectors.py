from django.db.models.query import QuerySet

from users.models import User

from .models import Notification


def get_notification_by_id(notification_id: int) -> Notification:
    return Notification.objects.get(pk=notification_id)


def find_notifications_by_user(user: User) -> QuerySet[Notification]:
    """Returns a queryset of notifications addressed to the specified
    user.
    """
    return Notification.objects.filter(recipient=user)


def get_unread_notifications_count_by_user(user: User) -> int:
    """Returns the total count of unread notifications addressed to the
    specified user.
    """
    return Notification.objects.filter(
        recipient=user, status=Notification.Status.UNREAD
    ).count()
