from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "notification_type",
        "level",
        "title",
        "last_event_at",
        "read_at",
    )
    list_filter = (
        "notification_type",
        "level",
        "read_at",
        "last_event_at",
        "created_at",
    )
    search_fields = (
        "title",
        "body",
        "recipient__username",
        "recipient__email",
        "sender__username",
        "dedupe_key",
        "aggregate_key",
    )
    readonly_fields = (
        "level",
        "notification_type",
        "title",
        "body",
        "payload",
        "recipient",
        "sender",
        "dedupe_key",
        "aggregate_key",
        "created_at",
        "last_event_at",
        "read_at",
    )
    date_hierarchy = "last_event_at"
    ordering = ("-last_event_at", "-id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
