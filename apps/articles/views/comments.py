from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from ..forms import ArticleCommentForm
from ..models import Article
from ..services import toggle_comment_like


class ArticleCommentView(LoginRequiredMixin, View):
    def post(self, request, article_slug: str) -> HttpResponseRedirect:
        article = get_object_or_404(Article, slug=article_slug)
        form = ArticleCommentForm(request.POST, user=request.user, article=article)
        if form.is_valid():
            form.save()
        else:
            messages.error(request, "Your comment could not be posted.")
        return redirect(reverse("article-details", args=[article_slug]))


class CommentLikeView(LoginRequiredMixin, View):
    def post(self, request, comment_id: int) -> JsonResponse:
        data = {"likes": toggle_comment_like(comment_id, request.user.id)}
        return JsonResponse({"status": "success", "data": data}, status=200)
