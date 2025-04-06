from django.contrib import admin
from django.utils.html import format_html

from users.models import Profile, User


admin.site.register(User)


@admin.register(Profile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "get_profile_image")
    search_fields = ("user__username",)
    readonly_fields = ("user",)

    def get_profile_image(self, profile):
        return format_html(f"<img src={profile.image.url} width='35' height='35'>")
