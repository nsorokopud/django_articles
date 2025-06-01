from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.db.models import QuerySet
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_filters.views import FilterView

from articles import selectors, services
from articles.filters import ArticleFilter
from articles.forms import ArticleCommentForm, ArticleCreateForm, ArticleUpdateForm
from articles.models import Article
from articles.settings import ARTICLES_PER_PAGE_COUNT
from articles.utils import AllowOnlyAuthorMixin


class ArticleListFilterView(FilterView):
    filterset_class = ArticleFilter
    context_object_name = "articles"
    paginate_by = ARTICLES_PER_PAGE_COUNT
    template_name = "articles/home_page.html"

    def get_queryset(self) -> QuerySet[Article]:
        return selectors.find_published_articles()


class HomePageView(View):
    def get(self, request):
        return redirect("articles")


class ArticleDetailView(DetailView):
    model = Article
    slug_url_kwarg = "article_slug"
    context_object_name = "article"
    template_name = "articles/article.html"

    def get_object(self):
        article_slug = self.kwargs.get(self.slug_url_kwarg)
        article = selectors.get_article_by_slug(article_slug)
        session_key = f"viewed_article_{article_slug}"
        if not self.request.session.get(session_key):
            services.increment_article_views_counter(article)
            self.request.session[session_key] = True
        return article

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ArticleCommentForm()
        article_slug = self.kwargs["article_slug"]
        context["comments"] = selectors.find_comments_to_article(article_slug)
        context["comments_count"] = len(context["comments"])
        article = context["article"]
        context["user_liked"] = (
            self.request.user.is_authenticated
            and self.request.user in article.users_that_liked.all()
        )
        if self.request.user.is_authenticated:
            context["liked_comments"] = selectors.find_article_comments_liked_by_user(
                article_slug, self.request.user
            )
        return context


class ArticleCreateView(LoginRequiredMixin, CreateView):
    model = Article
    form_class = ArticleCreateForm
    template_name = "articles/article_form.html"
    login_url = reverse_lazy("login")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def post(self, request):
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["update"] = True
        return context

    def get_object(self):
        return selectors.get_article_by_slug(self.kwargs["article_slug"])

    def post(self, request, *args, **kwargs):
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


class ArticleCommentView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login")

    def post(self, request, article_slug):
        form = ArticleCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = get_object_or_404(Article, slug=article_slug)
            comment.author = request.user
            comment.save()
            return redirect(reverse("article-details", args=[article_slug]))


class ArticleLikeView(LoginRequiredMixin, View):
    def post(self, request, article_slug):
        user_id = request.user.id
        likes_count = services.toggle_article_like(article_slug, user_id)
        return JsonResponse({"likes_count": likes_count})


class CommentLikeView(LoginRequiredMixin, View):
    def post(self, request, comment_id):
        user_id = request.user.id
        likes_count = services.toggle_comment_like(comment_id, user_id)
        return JsonResponse({"comment_likes_count": likes_count})


class AttachedFileUploadView(LoginRequiredMixin, View):
    def post(self, request):
        file = request.FILES.get("file")
        article_id = request.POST.get("articleId")
        file_path, article_url = services.save_media_file_attached_to_article(
            file, article_id
        )
        data = {"location": default_storage.url(file_path), "articleUrl": article_url}
        return JsonResponse({"status": "success", "data": data})
