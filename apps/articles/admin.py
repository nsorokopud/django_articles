from django.contrib import admin

from articles.models import Article, ArticleCategory, ArticleComment


class CommentInline(admin.TabularInline):
    model = ArticleComment


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("id", "is_published", "title", "category", "author", "created_at")
    list_display_links = ("id", "title")
    list_editable = ("is_published",)
    list_filter = ("is_published", "created_at", "category", "author")
    search_fields = ("title", "author__username", "category__title")
    prepopulated_fields = {"slug": ("title",)}
    actions = ("publish", "unpublish")
    inlines = (CommentInline,)
    save_on_top = True
    save_as = True

    def publish(self, request, queryset):
        updated_rows_count = queryset.update(is_published=True)
        if updated_rows_count == 1:
            message = "1 article was published"
        else:
            message = f"{updated_rows_count} articles were published"
        self.message_user(request, message)

    def unpublish(self, request, queryset):
        updated_rows_count = queryset.update(is_published=False)
        if updated_rows_count == 1:
            message = "1 article was unpublished"
        else:
            message = f"{updated_rows_count} articles were unpublished"
        self.message_user(request, message)

    publish.short_description = "Publish selected articles"
    publish.allowed_permissions = ("change",)

    unpublish.short_description = "Unpublish selected articles"
    unpublish.allowed_permissions = ("change",)


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
