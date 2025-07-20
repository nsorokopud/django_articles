import logging
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_filters.views import FilterView

from core.decorators import cache_page_for_anonymous

from ..filters import ArticleFilter
from ..forms import ArticleCommentForm, ArticleModelForm
from ..models import Article
from ..selectors import (
    find_article_comments_liked_by_user,
    find_comments_to_article,
    find_published_articles,
    get_article_by_slug,
)
from ..services import toggle_article_like
from ..settings import ARTICLE_DETAILS_PAGE_CACHE_TIMEOUT, ARTICLES_PER_PAGE_COUNT
from .decorators import increment_article_view_counter
from .mixins import AllowOnlyAuthorMixin


logger = logging.getLogger(__name__)


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

    @method_decorator(increment_article_view_counter)
    @method_decorator(cache_page_for_anonymous(ARTICLE_DETAILS_PAGE_CACHE_TIMEOUT))
    def dispatch(self, request, *args, **kwargs) -> HttpResponse:
        return super().dispatch(request, *args, **kwargs)

    def get_object(self) -> Article:
        article_slug = self.kwargs.get(self.slug_url_kwarg)
        try:
            article = get_article_by_slug(article_slug)
        except Article.DoesNotExist as e:
            logger.warning("Article with '%s' slug not found.", article_slug)
            raise Http404("Article not found") from e
        return article

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        article = self.object
        context = super().get_context_data(**kwargs)
        context["comments"] = find_comments_to_article(article)
        context["comments_count"] = len(context["comments"])
        context["user_liked"] = (
            self.request.user.is_authenticated
            and article.users_that_liked.filter(id=self.request.user.id).exists()
        )
        if self.request.user.is_authenticated:
            context["form"] = ArticleCommentForm()
            context["liked_comments"] = find_article_comments_liked_by_user(
                article, self.request.user
            )
        return context


class ArticleCreateView(LoginRequiredMixin, CreateView):
    model = Article
    form_class = ArticleModelForm
    template_name = "articles/article_form.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form) -> JsonResponse:
        article = form.save()
        data = {
            "articleId": article.id,
            "articleSlug": article.slug,
            "articleUrl": article.get_absolute_url(),
        }
        return JsonResponse({"status": "success", "data": data})

    def form_invalid(self, form) -> JsonResponse:
        return JsonResponse({"status": "fail", "data": form.errors})


class ArticleUpdateView(AllowOnlyAuthorMixin, UpdateView):
    model = Article
    form_class = ArticleModelForm
    template_name_suffix = "_form"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["update"] = True
        return context

    def get_object(self) -> Article:
        return get_article_by_slug(self.kwargs["article_slug"])

    def form_valid(self, form) -> JsonResponse:
        article = form.save()
        data = {"articleUrl": article.get_absolute_url()}
        return JsonResponse({"status": "success", "data": data})

    def form_invalid(self, form) -> JsonResponse:
        return JsonResponse({"status": "fail", "data": form.errors})


class ArticleDeleteView(AllowOnlyAuthorMixin, DeleteView):
    model = Article
    context_object_name = "article"
    slug_url_kwarg = "article_slug"
    success_url = reverse_lazy("articles")


class ArticleLikeView(LoginRequiredMixin, View):
    def post(self, request, article_slug) -> JsonResponse:
        data = {"likes": toggle_article_like(article_slug, request.user.id)}
        return JsonResponse({"status": "success", "data": data}, status=200)
