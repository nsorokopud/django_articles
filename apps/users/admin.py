from allauth.account.admin import EmailAddressAdmin as AllauthEmailAddressAdmin
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.utils.html import format_html

from .forms import EmailAddressModelForm
from .models import Profile, TokenCounter, User


admin.site.register((TokenCounter, User))


@admin.register(Profile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "get_profile_image")
    search_fields = ("user__username",)
    readonly_fields = ("user",)

    def get_profile_image(self, profile):
        return format_html("<img src='{}' width='35' height='35' />", profile.image.url)


class EmailAddressAdmin(AllauthEmailAddressAdmin):
    form = EmailAddressModelForm


admin.site.unregister(EmailAddress)
admin.site.register(EmailAddress, EmailAddressAdmin)
