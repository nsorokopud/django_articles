import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import FormView
from django_ratelimit.decorators import ratelimit

from users.forms import EmailChangeConfirmationForm, EmailChangeForm

from ..models import PendingEmailChange
from ..selectors import get_pending_email_change
from ..services import change_email_address, send_email_change_link
from ..services.email_addresses import (
    create_pending_email_change,
    delete_pending_email_change,
)


logger = logging.getLogger(__name__)


@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="5/h", method="POST", block=True),
    name="dispatch",
)
@method_decorator(
    ratelimit(key="core.ratelimit.post_email", rate="3/h", method="POST", block=True),
    name="dispatch",
)
class EmailChangeView(LoginRequiredMixin, FormView):
    template_name = "users/email_change.html"
    form_class = EmailChangeForm
    success_url = reverse_lazy("email-change")

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pending_email"] = get_pending_email_change(self.request.user)
        return context

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form) -> HttpResponse:
        try:
            pending_email_change = create_pending_email_change(
                user_id=self.request.user.id,
                email=form.cleaned_data["new_email"],
            )
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

        base_url = self.request.build_absolute_uri("/")
        send_email_change_link(self.request.user, pending_email_change, base_url)

        messages.success(
            self.request,
            "Email change confirmation sent. Please check your new email address.",
        )
        return super().form_valid(form)


@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="1/m", method="POST", block=True),
    name="dispatch",
)
@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="10/d", method="POST", block=True),
    name="dispatch",
)
class EmailChangeResendView(LoginRequiredMixin, View):
    def post(self, request) -> HttpResponseRedirect:
        pending_email_change = get_pending_email_change(request.user)

        if pending_email_change:
            base_url = request.build_absolute_uri("/")
            send_email_change_link(request.user, pending_email_change, base_url)
            messages.info(
                request,
                (
                    "Email change confirmation re-sent. "
                    "Please check your new email address."
                ),
            )
            logger.info(
                (
                    "User(id=%s) requested a resend of the email change letter for "
                    "PendingEmailChange(id=%s)."
                ),
                request.user.id,
                pending_email_change.id,
            )
        else:
            logger.warning(
                "User(id=%s) asked to resend email change letter, but no "
                "pending email change was found.",
                request.user.id,
            )
            messages.info(
                request,
                "There is no pending email change to re-send a confirmation for.",
            )
        return redirect("email-change")


class EmailChangeCancelView(LoginRequiredMixin, View):
    def post(self, request) -> HttpResponseRedirect:
        pending_email_change = get_pending_email_change(request.user)

        if pending_email_change:
            pending_email_change_id = pending_email_change.id
            delete_pending_email_change(request.user)
            logger.info(
                "User(id=%s) cancelled pending email change; "
                "PendingEmailChange(id=%s) deleted.",
                request.user.id,
                pending_email_change_id,
            )
            messages.info(request, "Email change cancelled.")
        else:
            logger.warning(
                "User(id=%s) attempted to cancel email change, but no "
                "PendingEmailChange was found.",
                request.user.id,
            )
            messages.info(request, "No pending email change to cancel.")
        return redirect("email-change")


class EmailChangeConfirmationView(FormView):
    template_name = "users/email_change_confirm.html"
    form_class = EmailChangeConfirmationForm
    success_url = reverse_lazy("login")

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["pending_email_change_public_id"] = self.kwargs.get(
            "pending_email_change_public_id"
        )
        kwargs["token"] = self.kwargs.get("token")
        return kwargs

    def form_valid(self, form) -> HttpResponse:
        try:
            pending_email_change = PendingEmailChange.objects.only("id", "user_id").get(
                public_id=form.pending_email_change_public_id
            )

            change_email_address(
                user_id=pending_email_change.user_id,
                pending_email_change_id=pending_email_change.id,
                token=form.token,
            )
        except (PendingEmailChange.DoesNotExist, ValidationError):
            form.add_error(None, "This email change link is invalid or has expired.")
            return self.form_invalid(form)

        if self.request.user.is_authenticated:
            logout(self.request)

        messages.success(
            self.request,
            "Your email address was changed successfully. Please log in again.",
        )
        return super().form_valid(form)
