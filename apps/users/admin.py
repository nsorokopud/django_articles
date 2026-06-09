from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import PendingEmailChange, Profile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    readonly_fields = (
        "latest_article_publish_sequence",
        "subscriptions_last_seen_publish_sequence",
        "unread_notifications_count",
        "session_auth_version",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Article / notification / security state",
            {
                "fields": (
                    "latest_article_publish_sequence",
                    "subscriptions_last_seen_publish_sequence",
                    "unread_notifications_count",
                    "session_auth_version",
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


@admin.register(Profile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "get_profile_image", "notification_emails_allowed")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "image", "notification_emails_allowed")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

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
