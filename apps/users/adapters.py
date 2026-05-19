from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


class AccountAdapter(DefaultAccountAdapter):
    def get_password_change_redirect_url(self, request):
        return reverse("user-profile")

    def get_login_redirect_url(self, request):
        user = request.user
        if not user.has_usable_password():
            return reverse("password-set")
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        return self.get_login_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        if sociallogin.account.provider != "google":
            messages.error(request, "Unsupported social login provider.")
            raise ImmediateHttpResponse(redirect("login"))

        extra_data = sociallogin.account.extra_data or {}

        user_email = (sociallogin.user.email or "").strip().lower()
        google_email = (extra_data.get("email") or "").strip().lower()
        verified = extra_data.get("email_verified")

        if not user_email or not google_email:
            messages.error(request, "Google did not provide an email address.")
            raise ImmediateHttpResponse(redirect("login"))

        if verified is not True:
            messages.error(request, "Your Google email address is not verified.")
            raise ImmediateHttpResponse(redirect("login"))

        if google_email != user_email:
            messages.error(request, "Google account email mismatch.")
            raise ImmediateHttpResponse(redirect("login"))
