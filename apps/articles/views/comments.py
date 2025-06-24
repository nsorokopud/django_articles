from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View

from ..forms import ArticleCommentForm
from ..models import Article
from ..services import toggle_comment_like


class ArticleCommentView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login")

    def post(self, request, article_slug) -> HttpResponseRedirect:
        form = ArticleCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = get_object_or_404(Article, slug=article_slug)
            comment.author = request.user
            comment.save()
            return redirect(reverse("article-details", args=[article_slug]))


class CommentLikeView(LoginRequiredMixin, View):
    def post(self, request, comment_id) -> JsonResponse:
        user_id = request.user.id
        likes_count = toggle_comment_like(comment_id, user_id)
        return JsonResponse({"comment_likes_count": likes_count})
