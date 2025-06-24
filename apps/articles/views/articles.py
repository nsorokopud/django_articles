from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_filters.views import FilterView

from ..filters import ArticleFilter
from ..forms import ArticleCommentForm, ArticleCreateForm, ArticleUpdateForm
from ..models import Article
from ..selectors import (
    find_article_comments_liked_by_user,
    find_comments_to_article,
    find_published_articles,
    get_article_by_slug,
)
from ..services import increment_article_views_counter, toggle_article_like
from ..settings import ARTICLES_PER_PAGE_COUNT
from ..utils import AllowOnlyAuthorMixin


class ArticleListFilterView(FilterView):
    filterset_class = ArticleFilter
    context_object_name = "articles"
    paginate_by = ARTICLES_PER_PAGE_COUNT
    template_name = "articles/home_page.html"

    def get_queryset(self) -> QuerySet[Article]:
        return find_published_articles()


class ArticleDetailView(DetailView):
    model = Article
    slug_url_kwarg = "article_slug"
    context_object_name = "article"
    template_name = "articles/article.html"

    def get_object(self) -> Article:
        article_slug = self.kwargs.get(self.slug_url_kwarg)
        article = get_article_by_slug(article_slug)
        session_key = f"viewed_article_{article_slug}"
        if not self.request.session.get(session_key):
            increment_article_views_counter(article)
            self.request.session[session_key] = True
        return article

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["form"] = ArticleCommentForm()
        article_slug = self.kwargs["article_slug"]
        context["comments"] = find_comments_to_article(article_slug)
        context["comments_count"] = len(context["comments"])
        article = context["article"]
        context["user_liked"] = (
            self.request.user.is_authenticated
            and self.request.user in article.users_that_liked.all()
        )
        if self.request.user.is_authenticated:
            context["liked_comments"] = find_article_comments_liked_by_user(
                article_slug, self.request.user
            )
        return context


class ArticleCreateView(LoginRequiredMixin, CreateView):
    model = Article
    form_class = ArticleCreateForm
    template_name = "articles/article_form.html"
    login_url = reverse_lazy("login")

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def post(self, request) -> JsonResponse:
        form = ArticleCreateForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            article = form.save()
            data = {
                "articleId": article.id,
                "articleSlug": article.slug,
                "articleUrl": article.get_absolute_url(),
            }
            return JsonResponse({"status": "success", "data": data})
        return JsonResponse({"status": "fail", "data": form.errors})


class ArticleUpdateView(AllowOnlyAuthorMixin, UpdateView):
    model = Article
    fields = ["title", "category", "tags", "preview_text", "preview_image", "content"]
    login_url = reverse_lazy("login")
    template_name_suffix = "_form"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["update"] = True
        return context

    def get_object(self) -> Article:
        return get_article_by_slug(self.kwargs["article_slug"])

    def post(self, request, *args, **kwargs) -> JsonResponse:
        article = self.get_object()
        form = ArticleUpdateForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            article = form.save()
            data = {"articleUrl": article.get_absolute_url()}
            return JsonResponse({"status": "success", "data": data})
        return JsonResponse({"status": "fail", "data": form.errors})


class ArticleDeleteView(AllowOnlyAuthorMixin, DeleteView):
    model = Article
    context_object_name = "article"
    slug_url_kwarg = "article_slug"
    success_url = reverse_lazy("articles")


class ArticleLikeView(LoginRequiredMixin, View):
    def post(self, request, article_slug) -> JsonResponse:
        user_id = request.user.id
        likes_count = toggle_article_like(article_slug, user_id)
        return JsonResponse({"likes_count": likes_count})
