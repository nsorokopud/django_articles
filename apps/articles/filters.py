from django.db.models import QuerySet
from django.forms import TextInput
from django_filters import FilterSet
from django_filters.filters import (
    CharFilter,
    DateFromToRangeFilter,
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
    OrderingFilter,
)
from django_filters.widgets import DateRangeWidget
from django_select2.forms import Select2TagWidget

from users.models import User
from users.selectors import find_authors_subscribed_by_user, get_all_users

from .models import Article
from .selectors import (
    find_articles_by_query,
    find_articles_with_all_tags,
    get_all_categories,
    get_all_tags,
)


class ArticleFilter(FilterSet):
    q = CharFilter(
        method="search_filter",
        label="Search",
        widget=TextInput(attrs={"placeholder": "Enter text..."}),
    )
    author = ModelChoiceFilter(to_field_name="username")
    date = DateFromToRangeFilter(
        field_name="published_at",
        widget=DateRangeWidget(attrs={"type": "date"}),
        label="Date [after - before]",
    )
    category = ModelChoiceFilter(to_field_name="slug")
    tags = ModelMultipleChoiceFilter(
        to_field_name="name",
        method="tags_filter",
        widget=Select2TagWidget(attrs={"id": "filterTagsInput"}),
    )
    ordering = OrderingFilter(
        fields=(
            ("published_at", "published_at"),
            ("views_count", "views_count"),
            ("likes_count", "likes_count"),
        ),
        field_labels={
            "published_at": "Date and Time",
            "views_count": "Views",
            "likes_count": "Likes",
        },
    )

    class Meta:
        model = Article
        fields = ["q", "author", "date", "category", "tags", "ordering"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["author"].queryset = get_all_users()
        self.filters["category"].queryset = get_all_categories()
        self.filters["tags"].queryset = get_all_tags()

    def search_filter(self, queryset, name, value) -> QuerySet[Article]:
        if not value:
            return queryset
        return find_articles_by_query(value, queryset)

    def tags_filter(self, queryset, name, value) -> QuerySet[Article]:
        if not value:
            return queryset
        return find_articles_with_all_tags(value, queryset)


class SubscriptionFeedFilter(ArticleFilter):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user and user.is_authenticated:
            self.filters["author"].queryset = find_authors_subscribed_by_user(user)
        else:
            self.filters["author"].queryset = User.objects.none()
