from django.contrib import admin
from django.utils.safestring import mark_safe

from users.models import Profile


@admin.register(Profile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "get_profile_image")
    search_fields = ("user__username",)
    readonly_fields = ("user",)

    def get_profile_image(self, profile):
        return mark_safe(f"<img src={profile.image.url} width='35' height='35'>")
