from django.http import JsonResponse, HttpResponseForbidden

from django.views import View

from .services import (
    mark_notification_as_read,
    delete_notification,
    get_notification_by_id,
    get_unread_notifications_count_by_user,
)


class ReadNotificationView(View):
    def post(self, request, notification_id):
        notification = get_notification_by_id(notification_id)
        if notification.recipient == request.user:
            mark_notification_as_read(notification)
            return JsonResponse(
                {"status": "ok", "message": "notification status was changed to READ"}
            )
        return HttpResponseForbidden()


class DeleteNotificationView(View):
    def post(self, request, notification_id):
        notification = get_notification_by_id(notification_id)
        if notification.recipient == request.user:
            delete_notification(notification)
            unread_notifications_count = get_unread_notifications_count_by_user(request.user)
            return JsonResponse(
                {
                    "status": "ok",
                    "message": "notification was deleted successfully",
                    "unread_notifications_count": unread_notifications_count,
                }
            )
        return HttpResponseForbidden()
