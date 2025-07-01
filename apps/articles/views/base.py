import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views import View
from django.views.generic.base import RedirectView
from taggit.views import get_object_or_404

from core.exceptions import MediaSaveError

from ..forms import AttachedFileUploadForm
from ..models import Article
from ..services import save_media_file_attached_to_article


logger = logging.getLogger("default_logger")


class HomePageView(RedirectView):
    pattern_name = "articles"


class AttachedFileUploadView(LoginRequiredMixin, View):
    def post(self, request) -> JsonResponse:
        try:
            article_id = int(request.POST.get("articleId"))
        except (TypeError, ValueError):
            return self._error("Invalid or missing article ID", 400)

        article = get_object_or_404(Article, id=article_id)

        if request.user != article.author:
            return self._error("No permission to edit this article", 403)

        form = AttachedFileUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._error(form.errors["file"][0], 400)
        file = form.cleaned_data["file"]

        try:
            file_path, article_url = save_media_file_attached_to_article(file, article)
            data = {
                "location": default_storage.url(file_path),
                "articleUrl": article_url,
            }
            return JsonResponse({"status": "success", "data": data}, status=200)
        except MediaSaveError:
            logger.exception("Error while saving uploaded file.")
            return self._error("File saving error", 500)

    def _error(self, message, status) -> JsonResponse:
        return JsonResponse({"status": "error", "message": message}, status=status)
