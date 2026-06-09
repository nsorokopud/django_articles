from django.http import JsonResponse
from django.views import View

from ..selectors import (
    find_article_filter_author_suggestions,
    find_article_filter_tag_suggestions,
)


class ArticleTagAutocompleteView(View):
    def get(self, request) -> JsonResponse:
        q = request.GET.get("q", "")

        results = [
            {"id": tag.name, "text": tag.name}
            for tag in find_article_filter_tag_suggestions(q)
        ]

        return JsonResponse({"results": results})


class ArticleAuthorAutocompleteView(View):
    def get(self, request) -> JsonResponse:
        q = request.GET.get("q", "")

        results = [
            {"id": user.username, "text": user.username}
            for user in find_article_filter_author_suggestions(q)
        ]

        return JsonResponse({"results": results})
