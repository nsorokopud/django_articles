from django.http import Http404

from articles.services import get_all_categories


class AllowOnlyAuthorMixin:
    def dispatch(self, *args, **kwargs):
        if self.get_object().author != self.request.user:
            raise Http404
        return super().dispatch(*args, **kwargs)


class CategoriesMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = get_all_categories()
        return context
