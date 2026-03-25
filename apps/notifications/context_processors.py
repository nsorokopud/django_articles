from typing import Any

from .selectors.base import get_unread_notifications_count_by_user


def include_notification_count(request) -> dict[str, Any] | dict:
    user = getattr(request, "user", None)

    if user and getattr(user, "is_authenticated", False):
        return {
            "notification_count": get_unread_notifications_count_by_user(user.id),
        }
    return {}
