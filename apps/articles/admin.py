from django.contrib import admin

from .forms import ArticleAdminForm
from .models import Article, ArticleCategory, ArticleComment, ArticleStatus
from .services.publishing import publish_article, reject_article, unpublish_article


class CommentInline(admin.TabularInline):
    model = ArticleComment


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm
    list_display = (
        "id",
        "pub_seq",
        "status",
        "title",
        "category",
        "author",
        "created_at",
    )
    list_display_links = ("id", "title")
    list_filter = ("status", "published_at", "created_at", "category", "author")
    search_fields = ("title", "author__username", "category__title")
    readonly_fields = ("published_at", "publish_sequence", "created_at", "modified_at")
    prepopulated_fields = {"slug": ("title",)}
    actions = ("publish", "reject", "unpublish")
    inlines = (CommentInline,)
    save_on_top = True
    save_as = True

    @admin.display(description="PSeq", ordering="publish_sequence")
    def pub_seq(self, obj):
        return obj.publish_sequence if obj.publish_sequence is not None else "-"

    @admin.action(description="Publish selected articles", permissions=("change",))
    def publish(self, request, queryset):
        updated_rows_count = 0
        for article in queryset.exclude(status=ArticleStatus.PUBLISHED):
            publish_article(article_id=article.id)
            updated_rows_count += 1

        if updated_rows_count == 1:
            message = "1 article was published"
        else:
            message = f"{updated_rows_count} articles were published"
        self.message_user(request, message)

    @admin.action(description="Unpublish selected articles", permissions=("change",))
    def unpublish(self, request, queryset):
        updated_rows_count = 0
        for article in queryset.filter(status=ArticleStatus.PUBLISHED):
            unpublish_article(article_id=article.id)
            updated_rows_count += 1

        if updated_rows_count == 1:
            message = "1 article was unpublished"
        else:
            message = f"{updated_rows_count} articles were unpublished"
        self.message_user(request, message)

    @admin.action(description="Reject selected articles", permissions=("change",))
    def reject(self, request, queryset):
        updated_rows_count = 0
        for article in queryset.filter(status=ArticleStatus.DRAFT):
            reject_article(article_id=article.id)
            updated_rows_count += 1

        if updated_rows_count == 1:
            message = "1 article was rejected"
        else:
            message = f"{updated_rows_count} articles were rejected"
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
