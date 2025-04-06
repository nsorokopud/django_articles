from django.contrib import admin

from .models import Notification


class NotificationAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)


admin.site.register(Notification, NotificationAdmin)
