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
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from ..forms import AuthenticationForm


logger = logging.getLogger(__name__)


@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="10/m", method="POST", block=True),
    name="dispatch",
)
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


@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="10/h", method="POST", block=True),
    name="dispatch",
)
@method_decorator(
    ratelimit(key="core.ratelimit.post_email", rate="3/h", method="POST", block=True),
    name="dispatch",
)
class PasswordResetView(DjangoPasswordResetView):
    template_name = "users/password_reset.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form) -> HttpResponse:
        messages.success(
            self.request,
            "If an account exists for that email, we will send a password reset link "
            "shortly. If you do not receive it, please request a new link.",
        )
        return super().form_valid(form)


class UserPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "users/password_reset_confirm.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form) -> HttpResponse:
        messages.success(self.request, "Your password was reset successfully.")
        return super().form_valid(form)
