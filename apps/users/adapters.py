from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class AccountAdapter(DefaultAccountAdapter):
    def get_password_change_redirect_url(self, request):
        return reverse("articles")

    def get_login_redirect_url(self, request):
        user = request.user
        if not user.has_usable_password():
            return reverse("password-set")
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        return self.get_login_redirect_url(request)
