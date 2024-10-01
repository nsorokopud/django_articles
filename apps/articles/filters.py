from django_filters import FilterSet
from django_filters.filters import (
    CharFilter,
    DateFromToRangeFilter,
    OrderingFilter,
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
)
from django_filters.widgets import DateRangeWidget
from django_select2.forms import Select2TagWidget

from django.forms import TextInput

from users.services import get_all_users
from .models import Article
from .services import (
    find_articles_by_query,
    find_articles_with_tags,
    get_all_categories,
    get_all_tags,
)


class ArticleFilter(FilterSet):
    q = CharFilter(
        method="search_filter",
        label="Search",
        widget=TextInput(attrs={"placeholder": "Enter text..."}),
    )
    author = ModelChoiceFilter(queryset=get_all_users(), to_field_name="username")
    date = DateFromToRangeFilter(
        field_name="created_at",
        widget=DateRangeWidget(attrs={"type": "date"}),
        label="Date [after - before]",
    )
    category = ModelChoiceFilter(queryset=get_all_categories(), to_field_name="slug")
    tags = ModelMultipleChoiceFilter(
        queryset=get_all_tags(),
        to_field_name="name",
        method="tags_filter",
        widget=Select2TagWidget(attrs={"id": "filterTagsInput"}),
    )
    ordering = OrderingFilter(
        fields=[
            ("created_at", "Date and Time"),
            ("views_count", "Views"),
            ("likes_count", "Likes"),
        ],
    )

    class Meta:
        model = Article
        fields = ["q", "author", "date", "category", "tags", "ordering"]

    def search_filter(self, queryset, name, value):
        return find_articles_by_query(value, queryset)

    def tags_filter(self, queryset, name, value):
        return find_articles_with_tags(value, queryset)
