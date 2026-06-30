import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic.base import RedirectView
from django_ratelimit.decorators import ratelimit

from core.exceptions import MediaSaveError

from ..forms import AttachedFileUploadForm
from ..models import Article, ArticleStatus
from ..services.media import save_article_inline_media_file


logger = logging.getLogger(__name__)


class HomePageView(RedirectView):
    pattern_name = "articles"


@method_decorator(
    ratelimit(key="user", rate="10/s", method="POST", block=True), name="dispatch"
)
@method_decorator(
    ratelimit(key="user", rate="30/m", method="POST", block=True), name="dispatch"
)
@method_decorator(
    ratelimit(key="user", rate="100/h", method="POST", block=True), name="dispatch"
)
class AttachedFileUploadView(LoginRequiredMixin, View):
    def post(self, request) -> JsonResponse:
        try:
            article_id = int(request.POST.get("articleId"))
        except (TypeError, ValueError):
            return self._error("Invalid or missing article ID", 400)

        article = get_object_or_404(
            Article.objects.only("id", "author_id", "status"), id=article_id
        )

        if request.user.id != article.author_id:
            return self._error("No permission to edit this article.", 403)

        if article.status not in {ArticleStatus.DRAFT, ArticleStatus.REJECTED}:
            return self._error("This article cannot be edited.", 403)

        form = AttachedFileUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._error(form.errors["file"][0], 400)
        file = form.cleaned_data["file"]

        try:
            file_path = save_article_inline_media_file(file, article)
            data = {"location": default_storage.url(file_path)}
            return JsonResponse({"status": "success", "data": data}, status=200)
        except MediaSaveError:
            logger.exception("Error while saving uploaded file.")
            return self._error("File saving error", 500)

    def _error(self, message, status) -> JsonResponse:
        return JsonResponse({"status": "error", "message": message}, status=status)
