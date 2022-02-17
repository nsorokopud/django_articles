from django.http import Http404

from articles.constants import ARTICLES_PER_PAGE_COUNT
from articles.models import Article
from articles.services import get_all_categories


class AllowOnlyAuthorMixin:
    def dispatch(self, *args, **kwargs):
        if self.get_object().author != self.request.user:
            raise Http404()
        else:
            return super().dispatch(*args, **kwargs)


class ArticlesListMixin:
    model = Article
    context_object_name = "articles"
    paginate_by = ARTICLES_PER_PAGE_COUNT
    template_name = "articles/home_page.html"


class CategoriesMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = get_all_categories()
        return context
