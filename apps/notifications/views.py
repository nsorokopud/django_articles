from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import BadRequest
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET, require_POST

from core.http import get_int_param

from .selectors.base import get_unread_notifications_count_by_user
from .selectors.inbox import get_notifications_page
from .services.actions import delete_notification, mark_notification_as_read


@method_decorator(require_POST, name="dispatch")
class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, notification_id: int) -> JsonResponse:
        changed = mark_notification_as_read(notification_id, request.user.id)
        unread = get_unread_notifications_count_by_user(request.user.id)
        return JsonResponse(
            {
                "status": "ok",
                "changed": changed,
                "message": (
                    "notification marked as read successfully"
                    if changed
                    else "notification already marked as read or not found"
                ),
                "unread_notifications_count": unread,
            }
        )


@method_decorator(require_POST, name="dispatch")
class NotificationDeleteView(LoginRequiredMixin, View):
    def post(self, request, notification_id: int) -> JsonResponse:
        deleted = delete_notification(notification_id, request.user.id)
        unread = get_unread_notifications_count_by_user(request.user.id)
        return JsonResponse(
            {
                "status": "ok",
                "deleted": deleted,
                "message": (
                    "notification was deleted successfully"
                    if deleted
                    else "notification already deleted or not found"
                ),
                "unread_notifications_count": unread,
            }
        )


@require_GET
@login_required
def notifications_list(request) -> JsonResponse:
    try:
        limit = get_int_param(request, "limit", 50)
        after_id = get_int_param(request, "after_id", 0)
        before_id = get_int_param(request, "before_id", 0)
    except BadRequest as e:
        return JsonResponse({"error": str(e)}, status=400)

    data = get_notifications_page(
        user_id=request.user.id,
        limit=limit,
        after_id=after_id,
        before_id=before_id,
        include_read=request.GET.get("include_read", "1") == "1",
    )
    return JsonResponse(data)


@require_GET
@login_required
def notifications_unread_count(request) -> JsonResponse:
    unread_count = get_unread_notifications_count_by_user(request.user.id)
    return JsonResponse({"unread": unread_count})
