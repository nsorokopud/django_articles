from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from ..services import toggle_comment_like


class CommentLikeView(LoginRequiredMixin, View):
    def post(self, request, comment_id: int) -> JsonResponse:
        data = {"likes": toggle_comment_like(comment_id, request.user.id)}
        return JsonResponse({"status": "success", "data": data}, status=200)
