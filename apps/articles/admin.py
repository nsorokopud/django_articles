from django.contrib import admin

from .forms import ArticleAdminForm
from .models import Article, ArticleCategory, ArticleComment
from .services import generate_unique_article_slug
from .services.publishing import publish_article


class CommentInline(admin.TabularInline):
    model = ArticleComment


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm
    list_display = ("id", "published_at", "title", "category", "author", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("published_at", "created_at", "category", "author")
    search_fields = ("title", "author__username", "category__title")
    readonly_fields = ("published_at", "publish_sequence", "created_at", "modified_at")
    prepopulated_fields = {"slug": ("title",)}
    actions = ("publish", "unpublish")
    inlines = (CommentInline,)
    save_on_top = True
    save_as = True

    def save_model(self, request, obj, form, change):
        obj.from_admin = True
        if not obj.slug:
            obj.slug = generate_unique_article_slug(obj.title)
        super().save_model(request, obj, form, change)

    @admin.action(description="Publish selected articles", permissions=("change",))
    def publish(self, request, queryset):
        updated_rows_count = 0
        for article in queryset.filter(publish_sequence__isnull=True):
            publish_article(article_id=article.id)
            updated_rows_count += 1

        if updated_rows_count == 1:
            message = "1 article was published"
        else:
            message = f"{updated_rows_count} articles were published"
        self.message_user(request, message)

    @admin.action(description="Unpublish selected articles", permissions=("change",))
    def unpublish(self, request, queryset):
        updated_rows_count = queryset.filter(publish_sequence__isnull=False).update(
            published_at=None,
            publish_sequence=None,
        )
        if updated_rows_count == 1:
            message = "1 article was unpublished"
        else:
            message = f"{updated_rows_count} articles were unpublished"
        self.message_user(request, message)


@admin.register(ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "slug")
    list_display_links = ("id", "title", "slug")
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ArticleComment)
class ArticleCommentAdmin(admin.ModelAdmin):
    list_display = ("article", "author", "text")
    list_display_links = ("article", "text")
    list_filter = ("created_at", "author", "article")
    search_fields = ("article__title", "author__username")
    save_as = True
