from django_filters.views import FilterView

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import slugify
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from articles import services
from articles.constants import ARTICLES_PER_PAGE_COUNT
from articles.filters import ArticleFilter
from articles.forms import ArticleCreateForm, ArticleCommentForm
from articles.models import Article
from articles.utils import AllowOnlyAuthorMixin, CategoriesMixin


class ArticleListFilterView(FilterView):
    model = Article
    filterset_class = ArticleFilter
    context_object_name = "articles"
    paginate_by = ARTICLES_PER_PAGE_COUNT
    template_name = "articles/home_page.html"

    def get_queryset(self):
        return services.find_published_articles()


class HomePageView(View):
    def get(self, request):
        return redirect("articles")


class ArticleDetailView(CategoriesMixin, DetailView):
    model = Article
    slug_url_kwarg = "article_slug"
    context_object_name = "article"
    template_name = "articles/article.html"

    def get_object(self):
        article = super().get_object()
        article = services.get_article_by_slug(article.slug)
        services.increment_article_views_counter(article.slug)
        return article

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ArticleCommentForm()
        article_slug = self.kwargs["article_slug"]
        context["comments"] = services.find_comments_to_article(article_slug)
        context["comments_count"] = len(context["comments"])
        article = context["article"]
        if self.request.user in article.users_that_liked.all():
            context["user_liked"] = True
        context["liked_comments"] = services.find_article_comments_liked_by_user(
            article_slug, self.request.user
        )
        return context


class ArticleCreateView(LoginRequiredMixin, CategoriesMixin, CreateView):
    model = Article
    form_class = ArticleCreateForm
    template_name = "articles/article_form.html"
    login_url = reverse_lazy("login")

    def get_form_kwargs(self):
        kwargs = super(ArticleCreateView, self).get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def post(self, request):
        form = ArticleCreateForm(request.POST, request=request)
        if form.is_valid():
            article = form.save()
            data = {"articleId": article.id, "articleUrl": article.get_absolute_url()}
            return JsonResponse({"status": "success", "data": data})
        return JsonResponse({"status": "fail", "data": form.errors})


class ArticleUpdateView(AllowOnlyAuthorMixin, UpdateView):
    model = Article
    fields = ["title", "category", "tags", "preview_text", "preview_image", "content"]
    slug_url_kwarg = "article_slug"
    login_url = reverse_lazy("login")
    template_name = "articles/article_update.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.slug = slugify(form.instance.title)
        return super().form_valid(form)


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


class ArticleLikeView(View):
    def post(self, request, article_slug):
        user_id = request.user.id
        likes_count = services.toggle_article_like(article_slug, user_id)
        return JsonResponse({"likes_count": likes_count})


class CommentLikeView(View):
    def post(self, request, comment_id):
        user_id = request.user.id
        likes_count = services.toggle_comment_like(comment_id, user_id)
        return JsonResponse({"comment_likes_count": likes_count})


class AttachedFileUploadView(LoginRequiredMixin, View):
    def post(self, request):
        file = request.FILES.get("file")
        article_id = request.POST.get("articleId")
        file_path, article_url = services.save_media_file_attached_to_article(file, article_id)
        data = {"location": default_storage.url(file_path), "articleUrl": article_url}
        return JsonResponse({"status": "success", "data": data})
