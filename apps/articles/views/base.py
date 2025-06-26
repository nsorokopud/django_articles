from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views import View
from django.views.generic.base import RedirectView

from ..services import save_media_file_attached_to_article


class HomePageView(RedirectView):
    pattern_name = "articles"


class AttachedFileUploadView(LoginRequiredMixin, View):
    def post(self, request) -> JsonResponse:
        file = request.FILES.get("file")
        article_id = request.POST.get("articleId")
        file_path, article_url = save_media_file_attached_to_article(file, article_id)
        data = {"location": default_storage.url(file_path), "articleUrl": article_url}
        return JsonResponse({"status": "success", "data": data})
