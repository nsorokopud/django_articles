import logging
from typing import Any, Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, UpdateView
from django_filters.views import FilterView
from django_ratelimit.decorators import ratelimit

from core.decorators import cache_page_for_anonymous
from users.services.subscriptions import (
    advance_subscriptions_last_seen_publish_sequence,
)

from ..exceptions import ArticleCommentError
from ..filters import ArticleFilter, SubscriptionFeedFilter
from ..forms import ArticleCommentForm, ArticleModelForm
from ..media_paths import normalize_url_prefix
from ..models import Article, ArticleStatus
from ..selectors import (
    find_articles_by_author,
    find_published_articles,
    find_subscription_feed_articles,
    get_article_for_author_by_id,
    get_published_article_by_slug,
)
from ..services.comments import get_article_comments_page
from ..services.editing import delete_article, get_or_create_empty_draft
from ..services.likes import set_article_like
from ..services.publishing import (
    submit_article_for_review,
    withdraw_article_from_review,
)
from .decorators import increment_article_view_counter
from .http import parse_liked_payload


logger = logging.getLogger(__name__)


class BaseArticleListFilterView(FilterView):
    context_object_name = "articles"
    paginate_by = settings.ARTICLES_PER_PAGE
    template_name = "articles/article_list_page.html"

    page_title = ""
    empty_message = ""
    show_filters = True
    show_views = True
    show_likes = True
    show_comments = True
    draft_edit_url_name = None
    author_filter_ajax_enabled = True

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
                "author_filter_ajax_enabled": self.author_filter_ajax_enabled,
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
    author_filter_ajax_enabled = False

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
    paginate_by = settings.ARTICLES_PER_PAGE
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

    def get_object(self) -> Article:
        article_slug = self.kwargs.get(self.slug_url_kwarg)
        try:
            article = get_published_article_by_slug(article_slug)
        except Article.DoesNotExist as e:
            logger.warning("Published article with '%s' slug not found.", article_slug)
            raise Http404("Article not found") from e
        return article

    @method_decorator(increment_article_view_counter)
    @method_decorator(
        cache_page_for_anonymous(settings.ARTICLES_DETAIL_PAGE_CACHE_TIMEOUT_SECONDS)
    )
    def get(self, request, *args, **kwargs) -> HttpResponse:
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        article = self.object
        context = super().get_context_data(**kwargs)

        comments_page, liked_comments = get_article_comments_page(
            article=article, page_number=1, user=self.request.user
        )

        context["comments"] = comments_page.object_list
        context["comments_page_obj"] = comments_page
        context["comments_count"] = article.comments_count

        context["user_liked"] = (
            self.request.user.is_authenticated
            and article.users_that_liked.filter(id=self.request.user.id).exists()
        )

        if self.request.user.is_authenticated:
            context["form"] = kwargs.get("form") or ArticleCommentForm()
            context["liked_comments"] = liked_comments

        return context

    @method_decorator(
        ratelimit(
            key="core.ratelimit.user_or_ip", rate="5/m", method="POST", block=True
        )
    )
    def post(self, request, *args, **kwargs) -> HttpResponse | HttpResponseRedirect:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        self.object = self.get_object()
        form = ArticleCommentForm(request.POST, user=request.user, article=self.object)

        if form.is_valid():
            try:
                form.save()
            except ArticleCommentError as e:
                form.add_error(None, str(e))
                messages.error(request, "Your comment could not be posted.")
                return self.render_to_response(
                    self.get_context_data(form=form), status=400
                )

            messages.success(request, "Your comment has been posted.")
            return redirect("article-details", article_slug=self.object.slug)

        messages.error(request, "Your comment could not be posted.")
        return self.render_to_response(self.get_context_data(form=form), status=400)


@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="10/h", method="POST", block=True),
    name="dispatch",
)
class ArticleCreateDraftView(LoginRequiredMixin, View):
    def post(self, request) -> HttpResponseRedirect:
        article = get_or_create_empty_draft(author=request.user)
        return redirect("article-update", pk=article.pk)


class ArticleUpdateView(LoginRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleModelForm
    template_name_suffix = "_form"

    object: Optional[Article] = None

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["update"] = True

        media_allowed_root_urls = []

        for url in getattr(settings, "MEDIA_ALLOWED_ROOT_URLS", []):
            normalized_url = normalize_url_prefix(url)
            if normalized_url:
                media_allowed_root_urls.append(normalized_url)

        context["media_allowed_root_urls"] = media_allowed_root_urls

        return context

    def get_object(self, queryset=None) -> Article:
        if self.object is not None:
            return self.object

        try:
            self.object = get_article_for_author_by_id(
                article_id=self.kwargs["pk"], author_id=self.request.user.id
            )
        except Article.DoesNotExist as e:
            raise Http404("Article not found") from e

        return self.object

    def dispatch(self, request, *args, **kwargs) -> HttpResponse | HttpResponseRedirect:
        if request.user.is_anonymous:
            return self.handle_no_permission()

        article = self.get_object()

        if article.status == ArticleStatus.PUBLISHED:
            return redirect("article-details", article_slug=article.slug)

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form) -> JsonResponse:
        article = form.save()

        if self.request.POST.get("article_action") == "submit_for_review":
            try:
                article = submit_article_for_review(article_id=article.id)
            except ValueError as e:
                return JsonResponse(
                    {"status": "fail", "data": {"__all__": [str(e)]}}, status=400
                )

            messages.success(self.request, "Article was submitted for review.")

        data = {
            "articleUrl": reverse("article-update", kwargs={"pk": article.pk}),
        }
        return JsonResponse({"status": "success", "data": data})

    def form_invalid(self, form) -> JsonResponse:
        return JsonResponse({"status": "fail", "data": form.errors}, status=400)


class ArticleWithdrawFromReviewView(LoginRequiredMixin, View):
    def post(self, request, pk) -> HttpResponseRedirect:
        try:
            article = get_article_for_author_by_id(
                article_id=pk, author_id=request.user.id
            )
        except Article.DoesNotExist as e:
            raise Http404("Article not found") from e

        try:
            withdraw_article_from_review(article_id=article.id)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "Article was withdrawn from review.")

        return redirect("article-update", pk=article.pk)


class ArticleDeleteView(LoginRequiredMixin, DeleteView):
    model = Article
    context_object_name = "article"
    success_url = reverse_lazy("my-articles")

    def get_queryset(self):
        return Article.objects.filter(
            author=self.request.user,
            status__in=(ArticleStatus.DRAFT, ArticleStatus.REJECTED),
        )

    def form_valid(self, form) -> HttpResponseRedirect:
        article = self.get_object()

        try:
            delete_article(article_id=article.id)
        except ValueError as e:
            raise PermissionDenied("This article cannot be deleted.") from e

        messages.success(
            self.request,
            f'"{article.title or "Article"}" was deleted successfully.',
        )
        return HttpResponseRedirect(self.get_success_url())


@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="120/h", method="POST", block=True),
    name="dispatch",
)
class ArticleLikeView(LoginRequiredMixin, View):
    def post(self, request, article_slug) -> JsonResponse:
        liked = parse_liked_payload(request)
        if liked is None:
            return JsonResponse(
                {"status": "fail", "message": "'liked' must be true or false."},
                status=400,
            )

        likes, liked = set_article_like(
            article_slug=article_slug, user_id=request.user.id, liked=liked
        )

        return JsonResponse(
            {"status": "success", "data": {"likes": likes, "liked": liked}}
        )
