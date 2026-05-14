from allauth.account.admin import EmailAddressAdmin as AllauthEmailAddressAdmin
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .forms import EmailAddressModelForm
from .models import Profile, TokenCounter, User


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


class EmailAddressAdmin(AllauthEmailAddressAdmin):
    form = EmailAddressModelForm


admin.site.unregister(EmailAddress)
admin.site.register(EmailAddress, EmailAddressAdmin)
