import logging
from typing import Any

from .services import find_notifications_by_user, get_unread_notifications_count_by_user


logger = logging.getLogger(__name__)


def include_user_notifications(request) -> dict[str, Any] | dict:
    user = getattr(request, "user", None)

    if user is None:
        logger.warning(
            "Request (%s) has no user attribute. Path: %s.",
            type(request),
            request.get_full_path(),
        )

    if user and getattr(user, "is_authenticated", False):
        return {
            "notifications": find_notifications_by_user(user.id),
            "notifications_count": get_unread_notifications_count_by_user(user),
        }
    return {}
