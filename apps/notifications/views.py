from django.http import JsonResponse, HttpResponseForbidden
from django.views import View

from .services import mark_notification_as_read, get_notification_by_id


class ReadNotificationView(View):
    def post(self, request, notification_id):
        notification = get_notification_by_id(notification_id)
        if notification.recipient == request.user:
            mark_notification_as_read(notification)
            return JsonResponse(
                {"status": "ok", "message": "notification status was changed to READ"}
            )
        return HttpResponseForbidden()
