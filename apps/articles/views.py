from django.views.generic import ListView, DetailView

from .models import Article
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
