import logging
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from django_filters.views import FilterView

from core.decorators import cache_page_for_anonymous
from users.services.subscriptions import (
    advance_subscriptions_last_seen_publish_sequence,
)

from ..filters import ArticleFilter, SubscriptionFeedFilter
from ..forms import ArticleCommentForm, ArticleModelForm
from ..models import Article
from ..selectors import (
    find_article_comments_liked_by_user,
    find_articles_by_author,
    find_comments_to_article,
    find_published_articles,
    find_subscription_feed_articles,
    get_article_for_author_by_slug,
    get_published_article_by_slug,
)
from ..services import toggle_article_like
from ..settings import ARTICLE_DETAILS_PAGE_CACHE_TIMEOUT, ARTICLES_PER_PAGE_COUNT
from .decorators import increment_article_view_counter
from .mixins import AllowOnlyAuthorMixin


logger = logging.getLogger(__name__)


class BaseArticleListFilterView(FilterView):
    context_object_name = "articles"
    paginate_by = ARTICLES_PER_PAGE_COUNT
    template_name = "articles/article_list_page.html"

    page_title = ""
    empty_message = ""
    show_filters = True
    show_views = True
    show_likes = True
    show_comments = True
    draft_edit_url_name = None

    page_key = ""
    is_subscriptions_feed_page_one = False
    latest_article_publish_sequence = 0

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        current_path = self.request.path
        context.update(
            {
                "page_title": self.page_title,
                "empty_message": self.empty_message,
                "show_filters": self.show_filters,
                "reset_url": current_path,
                "category_filter_url": current_path,
                "tag_filter_url": current_path,
                "show_views": self.show_views,
                "show_likes": self.show_likes,
                "show_comments": self.show_comments,
                "draft_edit_url_name": self.draft_edit_url_name,
                "page_key": self.page_key,
                "is_subscriptions_feed_page_one": self.is_subscriptions_feed_page_one,
                "latest_article_publish_sequence": self.latest_article_publish_sequence,
            }
        )
        return context


class ArticleListFilterView(BaseArticleListFilterView):
    filterset_class = ArticleFilter
    page_title = "Articles matching your query"
    empty_message = "No articles matching your query"

    def get_queryset(self) -> QuerySet[Article]:
        return find_published_articles()


class SubscriptionFeedView(LoginRequiredMixin, BaseArticleListFilterView):
    filterset_class = SubscriptionFeedFilter
    page_title = "Subscription feed"
    empty_message = "No matching articles from your subscriptions yet"
    page_key = "subscriptions"

    def get_queryset(self) -> QuerySet[Article]:
        return find_subscription_feed_articles(self.request.user)

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        page_obj = context.get("page_obj")
        articles = context.get("articles")

        is_page_one = bool(page_obj and page_obj.number == 1)

        latest_publish_sequence = 0
        first_article = next(iter(articles), None) if articles else None
        if first_article and first_article.publish_sequence:
            latest_publish_sequence = first_article.publish_sequence

        if is_page_one and latest_publish_sequence > 0:
            advance_subscriptions_last_seen_publish_sequence(
                user_id=self.request.user.id,
                last_seen_publish_sequence=latest_publish_sequence,
            )

        context.update(
            {
                "page_key": self.page_key,
                "is_subscriptions_feed_page_one": is_page_one,
                "latest_article_publish_sequence": latest_publish_sequence,
            }
        )
        return context


class MyArticlesListView(LoginRequiredMixin, ListView):
    model = Article
    context_object_name = "articles"
    paginate_by = ARTICLES_PER_PAGE_COUNT
    template_name = "articles/article_list_page.html"

    def get_queryset(self) -> QuerySet[Article]:
        return find_articles_by_author(self.request.user)

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        current_path = self.request.path
        context.update(
            {
                "page_title": "Your articles",
                "empty_message": "You have not created any articles yet",
                "show_filters": False,
                "reset_url": current_path,
                "category_filter_url": current_path,
                "tag_filter_url": current_path,
                "show_views": True,
                "show_likes": True,
                "show_comments": True,
                "draft_edit_url_name": "article-update",
                "page_key": "my-articles",
                "is_subscriptions_feed_page_one": False,
                "latest_article_publish_sequence": 0,
            }
        )
        return context


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
            article = get_published_article_by_slug(article_slug)
        except Article.DoesNotExist as e:
            logger.warning("Published article with '%s' slug not found.", article_slug)
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
        publish = self.request.user.is_staff or self.request.user.is_superuser
        article = form.save(publish=publish)

        article_url = (
            article.get_absolute_url()
            if article.publish_sequence is not None
            else reverse("article-update", kwargs={"article_slug": article.slug})
        )

        data = {
            "articleId": article.id,
            "articleSlug": article.slug,
            "articleUrl": article_url,
            "isPublished": article.publish_sequence is not None,
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
        try:
            return get_article_for_author_by_slug(
                article_slug=self.kwargs["article_slug"],
                author_id=self.request.user.id,
            )
        except Article.DoesNotExist as e:
            raise Http404("Article not found") from e

    def form_valid(self, form) -> JsonResponse:
        article = form.save(publish=False)

        article_url = (
            article.get_absolute_url()
            if article.publish_sequence is not None
            else reverse("article-update", kwargs={"article_slug": article.slug})
        )

        data = {
            "articleUrl": article_url,
            "isPublished": article.publish_sequence is not None,
        }
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
