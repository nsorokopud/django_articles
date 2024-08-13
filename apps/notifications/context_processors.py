from .services import (
    find_notifications_by_user,
    get_unread_notifications_count_by_user,
)


def include_user_notifications(request):
    if request.user.is_authenticated:
        notifications = find_notifications_by_user(request.user.id)
        notifications_count = get_unread_notifications_count_by_user(request.user)
        return {"notifications": notifications, "notifications_count": notifications_count}
    return {}
