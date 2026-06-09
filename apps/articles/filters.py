from django.db.models import QuerySet
from django.forms import Select, SelectMultiple, TextInput
from django_filters import FilterSet
from django_filters.filters import (
    CharFilter,
    DateFromToRangeFilter,
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
    OrderingFilter,
)
from django_filters.widgets import DateRangeWidget
from taggit.models import Tag

from users.models import User
from users.selectors import find_authors_subscribed_by_user

from .models import Article, ArticleStatus
from .selectors import (
    find_article_filter_authors,
    find_article_filter_categories,
    find_article_filter_tags,
    find_articles_by_query,
    find_articles_with_all_tags,
)


class ArticleFilter(FilterSet):
    q = CharFilter(
        method="search_filter",
        label="Search",
        widget=TextInput(attrs={"placeholder": "Enter text..."}),
    )
    author = ModelChoiceFilter(
        to_field_name="username",
        widget=Select(attrs={"id": "filterAuthorInput", "class": "author-select"}),
    )
    date = DateFromToRangeFilter(
        field_name="published_at",
        widget=DateRangeWidget(attrs={"type": "date"}),
        label="Date [after - before]",
    )
    category = ModelChoiceFilter(to_field_name="slug")
    tags = ModelMultipleChoiceFilter(
        to_field_name="name",
        method="tags_filter",
        widget=SelectMultiple(attrs={"id": "filterTagsInput"}),
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        data = self.data if self.is_bound else None

        selected_author = data.get("author") if data else None
        selected_tags = []

        if data:
            if hasattr(data, "getlist"):
                selected_tags = data.getlist("tags")
            else:
                raw_tags = data.get("tags", [])
                selected_tags = raw_tags if isinstance(raw_tags, list) else [raw_tags]

            selected_tags = [tag for tag in selected_tags if tag]

        self.filters["category"].queryset = find_article_filter_categories()

        if selected_author:
            self.filters["author"].queryset = find_article_filter_authors().filter(
                username=selected_author
            )
        else:
            self.filters["author"].queryset = User.objects.none()

        if selected_tags:
            self.filters["tags"].queryset = find_article_filter_tags().filter(
                name__in=selected_tags
            )
        else:
            self.filters["tags"].queryset = Tag.objects.none()

    def search_filter(self, queryset, name, value) -> QuerySet[Article]:
        if not value:
            return queryset
        return find_articles_by_query(value, queryset)

    def tags_filter(self, queryset, name, value) -> QuerySet[Article]:
        if not value:
            return queryset
        return find_articles_with_all_tags(value, queryset)


class SubscriptionFeedFilter(ArticleFilter):
    def __init__(self, *args, **kwargs) -> None:
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user and user.is_authenticated:
            self.filters["author"].queryset = (
                find_authors_subscribed_by_user(user)
                .filter(article__status=ArticleStatus.PUBLISHED)
                .distinct()
            )
        else:
            self.filters["author"].queryset = User.objects.none()
