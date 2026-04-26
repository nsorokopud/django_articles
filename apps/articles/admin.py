from typing import Optional

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html_join

from .forms import ArticleAdminForm, ArticleRejectAdminForm
from .models import Article, ArticleCategory, ArticleComment, ArticleStatus
from .services.articles import delete_article, save_article
from .services.publishing import publish_article, reject_article, unpublish_article


class CommentInline(admin.TabularInline):
    model = ArticleComment
    extra = 0
    can_delete = True
    show_change_link = True
    readonly_fields = ("author", "text", "created_at", "likes_count")
    fields = ("author", "text", "created_at", "likes_count")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_likes_count=Count("users_that_liked", distinct=True))

    @admin.display(description="Likes")
    def likes_count(self, obj):
        return getattr(obj, "_likes_count", 0)


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
    readonly_fields = (
        "status",
        "published_at",
        "publish_sequence",
        "review_note",
        "reviewed_at",
        "reviewed_by",
        "created_at",
        "modified_at",
        "workflow_buttons",
    )
    prepopulated_fields = {"slug": ("title",)}
    actions = ("publish", "unpublish")
    inlines = (CommentInline,)
    save_on_top = True
    save_as = False

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "slug",
                    "category",
                    "tags",
                    "author",
                    "preview_text",
                    "preview_image",
                    "content",
                )
            },
        ),
        (
            "Publication",
            {
                "fields": (
                    "status",
                    "published_at",
                    "publish_sequence",
                    "workflow_buttons",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "modified_at")},
        ),
        (
            "Review",
            {
                "fields": (
                    "review_note",
                    "reviewed_at",
                    "reviewed_by",
                )
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = tuple(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly += ("author",)
        return readonly

    def save_model(self, request, obj, form, change):
        """Prevents regular admin saves from changing workflow state
        (should only be changed via dedicated workflow actions).
        """
        if change:
            old_obj = Article.objects.only(
                "status",
                "published_at",
                "publish_sequence",
                "review_note",
                "reviewed_at",
                "reviewed_by",
            ).get(pk=obj.pk)
            obj.status = old_obj.status
            obj.published_at = old_obj.published_at
            obj.publish_sequence = old_obj.publish_sequence
            obj.review_note = old_obj.review_note
            obj.reviewed_at = old_obj.reviewed_at
            obj.reviewed_by = old_obj.reviewed_by

        save_article(
            article=obj,
            author=None if change else obj.author,
            restore_rejected_to_draft=False,
        )

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status in {
            ArticleStatus.PUBLISHED,
            ArticleStatus.PENDING_REVIEW,
        }:
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        try:
            delete_article(article_id=obj.id)
        except ValueError as e:
            self.message_user(request, str(e), level=messages.ERROR)
            raise PermissionDenied(str(e)) from e

    def delete_queryset(self, request, queryset):
        deleted_count = 0
        failures = []

        for article in queryset:
            try:
                delete_article(article_id=article.id)
            except ValueError as e:
                failures.append(f"#{article.id}: {e}")
            else:
                deleted_count += 1

        if deleted_count:
            self.message_user(
                request,
                f"{deleted_count} "
                f"article{' was' if deleted_count == 1 else 's were'} deleted.",
                level=messages.SUCCESS,
            )

        if failures:
            preview = "; ".join(failures[:5])
            suffix = "" if len(failures) <= 5 else f" (and {len(failures) - 5} more)"

            self.message_user(
                request,
                f"{len(failures)} selected "
                f"article{' was' if len(failures) == 1 else 's were'} not deleted: "
                f"{preview}{suffix}",
                level=messages.ERROR,
            )

    @admin.display(description="PSeq", ordering="publish_sequence")
    def pub_seq(self, obj):
        return obj.publish_sequence if obj.publish_sequence is not None else "-"

    @admin.display(description="Workflow")
    def workflow_buttons(self, obj):
        if not obj.pk:
            return "Save the article first to use workflow actions."

        buttons = []

        if obj.status == ArticleStatus.PENDING_REVIEW:
            buttons.extend(
                [
                    (
                        reverse("admin:articles_article_publish", args=[obj.pk]),
                        "Publish",
                    ),
                    (
                        reverse("admin:articles_article_reject", args=[obj.pk]),
                        "Reject",
                    ),
                ]
            )
        elif obj.status == ArticleStatus.PUBLISHED:
            buttons.append(
                (
                    reverse("admin:articles_article_unpublish", args=[obj.pk]),
                    "Unpublish",
                )
            )

        if not buttons:
            return "-"

        return format_html_join(
            "",
            (
                '<span style="margin-right: 8px;">'
                '<a class="button" href="{}">{}</a></span>'
            ),
            buttons,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:article_id>/publish/",
                self.admin_site.admin_view(self.process_publish),
                name="articles_article_publish",
            ),
            path(
                "<int:article_id>/unpublish/",
                self.admin_site.admin_view(self.process_unpublish),
                name="articles_article_unpublish",
            ),
            path(
                "<int:article_id>/reject/",
                self.admin_site.admin_view(self.process_reject),
                name="articles_article_reject",
            ),
        ]
        return custom_urls + urls

    def _get_article_or_404(self, request: HttpRequest, article_id: int) -> Article:
        article = self.get_object(request, article_id)
        if article is None:
            raise Http404("Article not found.")
        if not self.has_change_permission(request, article):
            raise PermissionDenied
        return article

    def _render_workflow_confirmation(  # pylint: disable=R0913
        self,
        request: HttpRequest,
        *,
        article: Article,
        action: str,
        title: str,
        confirm_label: str,
        form: Optional[ArticleRejectAdminForm] = None,
    ):
        opts = self.model._meta
        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "original": article,
            "object_id": article.pk,
            "title": title,
            "article": article,
            "action": action,
            "confirm_label": confirm_label,
            "back_url": reverse("admin:articles_article_change", args=[article.pk]),
            "form": form,
        }
        return TemplateResponse(
            request,
            "articles/admin/workflow_confirm.html",
            context,
        )

    def process_publish(self, request: HttpRequest, article_id: int):
        article = self._get_article_or_404(request, article_id)

        if request.method == "GET":
            return self._render_workflow_confirmation(
                request,
                article=article,
                action="publish",
                title=f"Confirm publish: {article}",
                confirm_label="Publish",
            )

        if request.method != "POST":
            raise PermissionDenied

        try:
            publish_article(article_id=article.id, actor=request.user)
        except ValueError as e:
            self.message_user(request, str(e), level=messages.ERROR)
        else:
            self.message_user(request, "Article was published.", level=messages.SUCCESS)

        return HttpResponseRedirect(
            reverse("admin:articles_article_change", args=[article.id])
        )

    def process_unpublish(self, request: HttpRequest, article_id: int):
        article = self._get_article_or_404(request, article_id)

        if request.method == "GET":
            return self._render_workflow_confirmation(
                request,
                article=article,
                action="unpublish",
                title=f"Confirm unpublish: {article}",
                confirm_label="Unpublish",
            )

        if request.method != "POST":
            raise PermissionDenied

        try:
            unpublish_article(article_id=article.id, actor=request.user)
        except ValueError as e:
            self.message_user(request, str(e), level=messages.ERROR)
        else:
            self.message_user(
                request,
                "Article was unpublished.",
                level=messages.SUCCESS,
            )

        return HttpResponseRedirect(
            reverse("admin:articles_article_change", args=[article.id])
        )

    def process_reject(self, request: HttpRequest, article_id: int):
        article = self._get_article_or_404(request, article_id)

        if request.method == "GET":
            form = ArticleRejectAdminForm(initial={"reason": article.review_note})
            return self._render_workflow_confirmation(
                request,
                article=article,
                action="reject",
                title=f"Confirm reject: {article}",
                confirm_label="Reject",
                form=form,
            )

        if request.method != "POST":
            raise PermissionDenied

        form = ArticleRejectAdminForm(request.POST)
        if not form.is_valid():
            return self._render_workflow_confirmation(
                request,
                article=article,
                action="reject",
                title=f"Confirm reject: {article}",
                confirm_label="Reject",
                form=form,
            )

        try:
            reject_article(
                article_id=article.id,
                reason=form.cleaned_data["reason"],
                reviewer=request.user,
            )
        except ValueError as e:
            self.message_user(request, str(e), level=messages.ERROR)
        else:
            self.message_user(request, "Article was rejected.", level=messages.SUCCESS)

        return HttpResponseRedirect(
            reverse("admin:articles_article_change", args=[article.id])
        )

    @admin.action(description="Publish selected articles", permissions=("change",))
    def publish(self, request, queryset):
        updated_rows_count = 0
        failures = []

        for article in queryset:
            try:
                publish_article(article_id=article.id, actor=request.user)
            except ValueError as e:
                failures.append(f"#{article.id}: {e}")
            else:
                updated_rows_count += 1

        if updated_rows_count:
            self.message_user(
                request,
                f"{updated_rows_count} "
                f"article{' was' if updated_rows_count == 1 else 's were'} published.",
                level=messages.SUCCESS,
            )

        if failures:
            preview = "; ".join(failures[:5])
            suffix = "" if len(failures) <= 5 else f" (and {len(failures) - 5} more)"
            self.message_user(
                request,
                f"Could not publish {len(failures)} selected "
                f"article{'s' if len(failures) != 1 else ''}: {preview}{suffix}",
                level=messages.ERROR,
            )

        if not updated_rows_count and not failures:
            self.message_user(
                request,
                "No selected articles were published.",
                level=messages.WARNING,
            )

    @admin.action(description="Unpublish selected articles", permissions=("change",))
    def unpublish(self, request, queryset):
        updated_rows_count = 0
        failures = []

        for article in queryset:
            try:
                unpublish_article(article_id=article.id, actor=request.user)
            except ValueError as e:
                failures.append(f"#{article.id}: {e}")
            else:
                updated_rows_count += 1

        if updated_rows_count:
            self.message_user(
                request,
                f"{updated_rows_count} "
                f"article{' was' if updated_rows_count == 1 else 's were'} "
                "unpublished.",
                level=messages.SUCCESS,
            )

        if failures:
            preview = "; ".join(failures[:5])
            suffix = "" if len(failures) <= 5 else f" (and {len(failures) - 5} more)"
            self.message_user(
                request,
                f"Could not unpublish {len(failures)} selected "
                f"article{'s' if len(failures) != 1 else ''}: {preview}{suffix}",
                level=messages.ERROR,
            )

        if not updated_rows_count and not failures:
            self.message_user(
                request,
                "No selected articles were unpublished.",
                level=messages.WARNING,
            )


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
