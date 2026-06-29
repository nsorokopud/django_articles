from django.contrib.auth.decorators import login_required
from django.core.exceptions import BadRequest
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core.http import get_int_param

from ..services.subscriptions import get_new_articles_summary


@require_GET
@login_required
def new_articles_summary(request) -> JsonResponse:
    try:
        since_publish_sequence = get_int_param(request, "since_publish_sequence", 0)
    except BadRequest as e:
        return JsonResponse({"error": str(e)}, status=400)

    data = get_new_articles_summary(
        user_id=request.user.id,
        since_publish_sequence=since_publish_sequence,
    )
    return JsonResponse(data)
