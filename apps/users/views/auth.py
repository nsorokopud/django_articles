import logging

from allauth.account.views import PasswordChangeView as AllauthPasswordChangeView
from allauth.account.views import PasswordSetView as AllauthPasswordSetView
from allauth.account.views import sensitive_post_parameters_m
from django.contrib import messages
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View

from users.forms import AuthenticationForm

from ..services.tokens import password_reset_token_generator


logger = logging.getLogger("default_logger")


class UserLoginView(LoginView):
    form_class = AuthenticationForm
    template_name = "users/login.html"


class PasswordChangeView(AllauthPasswordChangeView):
    template_name = "users/password_change.html"

    def form_valid(self, form) -> HttpResponse:
        response = super().form_valid(form)
        logger.info("Password changed for User(id=%s).", self.request.user.pk)
        return response


class PasswordSetView(AllauthPasswordSetView):
    template_name = "users/password_set.html"

    @sensitive_post_parameters_m
    def dispatch(self, request, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated or request.user.has_usable_password():
            raise PermissionDenied
        return View.dispatch(self, request, *args, **kwargs)


class PasswordResetView(DjangoPasswordResetView):
    template_name = "users/password_reset.html"
    token_generator = password_reset_token_generator
    success_url = reverse_lazy("login")

    def form_valid(self, form) -> HttpResponse:
        messages.success(
            self.request, "We've emailed you a link to reset your password."
        )
        return super().form_valid(form)


class UserPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "users/password_reset_confirm.html"
    token_generator = password_reset_token_generator
    success_url = reverse_lazy("login")

    def form_valid(self, form) -> HttpResponse:
        messages.success(self.request, "Your password was reset successfully.")
        return super().form_valid(form)
