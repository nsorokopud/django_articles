from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import PendingEmailChange, Profile, TokenCounter, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    readonly_fields = (
        "latest_article_publish_sequence",
        "subscriptions_last_seen_publish_sequence",
        "unread_notifications_count",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Article / notification state",
            {
                "fields": (
                    "latest_article_publish_sequence",
                    "subscriptions_last_seen_publish_sequence",
                    "unread_notifications_count",
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (("Email", {"fields": ("email",)}),)

    list_display = ("id", "username", "email", "is_active", "is_staff", "is_superuser")
    list_display_links = ("id", "username")
    search_fields = ("username", "email")
    ordering = ("username",)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))

        if obj is not None and "email" not in readonly_fields:
            readonly_fields.append("email")

        return tuple(readonly_fields)


@admin.register(TokenCounter)
class TokenCounterAdmin(admin.ModelAdmin):
    list_display = ("user", "token_type", "token_count")
    search_fields = ("user__username", "user__email", "token_type")
    list_filter = ("token_type",)
    readonly_fields = ("user", "token_type", "token_count")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Profile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "get_profile_image")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user",)

    @admin.display(description="Profile image")
    def get_profile_image(self, profile):
        if not profile.image:
            return "-"

        return format_html("<img src='{}' width='35' height='35' />", profile.image.url)


@admin.register(PendingEmailChange)
class PendingEmailChangeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "email", "created_at")
    list_display_links = ("id", "email")
    search_fields = ("user__username", "user__email", "email")
    readonly_fields = ("user", "email", "created_at")
    list_filter = ("created_at",)

    def has_add_permission(self, request):
        return False
