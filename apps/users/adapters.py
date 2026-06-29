from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from users.models import User
from users.services.accounts import activate_user

from .normalization import normalize_email


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

        user_email = normalize_email(sociallogin.user.email)
        google_email = normalize_email(extra_data.get("email"))
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

        existing_user = (
            User.objects.only("id", "is_active")
            .filter(email__iexact=google_email)
            .first()
        )

        if existing_user is None or existing_user.is_active:
            return

        # A verified Google email is accepted as proof of email ownership,
        # so it may activate an inactive local account with the same email
        activate_user(existing_user)

        # Keep allauth's in-memory user object in sync for this login flow
        existing_user.is_active = True
        if sociallogin.user.pk == existing_user.pk:
            sociallogin.user.is_active = True

        # Note: when allauth connects/authenticates a social account by verified email,
        # it may make an unverified local password unusable as a safety measure.
        # AccountAdapter.get_login_redirect_url() intentionally sends such users to
        # the password-set page.
