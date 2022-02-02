from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Article
from .forms import ArticleCreateForm
from .services import find_published_articles
from .utils import CategoriesMixin


class HomePageView(CategoriesMixin, ListView):
    model = Article
    context_object_name = "articles"
    paginate_by = 5
    template_name = "articles/home_page.html"

    def get_queryset(self):
        return find_published_articles()


class ArticleDetailView(CategoriesMixin, DetailView):
    model = Article
    slug_url_kwarg = "article_slug"
    context_object_name = "article"
    template_name = "articles/article.html"


class ArticleCreateView(LoginRequiredMixin, CategoriesMixin, CreateView):
    model = Article
    form_class = ArticleCreateForm
    template_name = "articles/article_create.html"
    login_url = reverse_lazy("login")

    def get_form_kwargs(self):
        kwargs = super(ArticleCreateView, self).get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs
