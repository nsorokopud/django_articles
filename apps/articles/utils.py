from .services import get_all_categories


class CategoriesMixin:
    def get_context_data(self):
        context = super().get_context_data()
        context["categories"] = get_all_categories()
        return context
