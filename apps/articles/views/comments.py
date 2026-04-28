from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.views import View

from ..models import Article
from ..selectors import get_published_article_by_slug
from ..services import toggle_comment_like
from ..services.comments import get_article_comments_page


class ArticleCommentsListView(View):
    def get(self, request, article_slug: str) -> JsonResponse:
        try:
            article = get_published_article_by_slug(article_slug)
        except Article.DoesNotExist as e:
            raise Http404("Article not found") from e

        comments_page, liked_comments = get_article_comments_page(
            article=article,
            page_number=request.GET.get("page"),
            user=request.user,
        )

        html = render_to_string(
            "articles/comment_list.html",
            {
                "comments": comments_page.object_list,
                "liked_comments": liked_comments,
                "request": request,
            },
            request=request,
        )

        return JsonResponse(
            {
                "status": "success",
                "html": html,
                "hasNext": comments_page.has_next(),
                "nextPage": (
                    comments_page.next_page_number()
                    if comments_page.has_next()
                    else None
                ),
            }
        )


class CommentLikeView(LoginRequiredMixin, View):
    def post(self, request, comment_id: int) -> JsonResponse:
        data = {"likes": toggle_comment_like(comment_id, request.user.id)}
        return JsonResponse({"status": "success", "data": data}, status=200)
