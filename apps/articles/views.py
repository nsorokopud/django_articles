from django.views.generic import ListView

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
