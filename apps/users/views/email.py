import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from users.forms import EmailChangeConfirmationForm, EmailChangeForm

from ..selectors import get_pending_email_address
from ..services import (
    change_email_address,
    create_pending_email_address,
    send_email_change_link,
)


logger = logging.getLogger(__name__)


class EmailChangeView(LoginRequiredMixin, FormView):
    template_name = "users/email_change.html"
    form_class = EmailChangeForm
    success_url = reverse_lazy("email-change")

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pending_email"] = get_pending_email_address(self.request.user)
        return context

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form) -> HttpResponse:
        new_email = create_pending_email_address(
            self.request.user, form.cleaned_data["new_email"]
        )
        base_url = self.request.build_absolute_uri("/")
        send_email_change_link(self.request.user, new_email.email, base_url)
        messages.success(
            self.request,
            "Email change confirmation sent. Please check your new email address.",
        )
        return super().form_valid(form)


class EmailChangeResendView(LoginRequiredMixin, View):
    def post(self, request) -> HttpResponseRedirect:
        email = get_pending_email_address(request.user)
        if email:
            base_url = request.build_absolute_uri("/")
            send_email_change_link(self.request.user, email.email, base_url)
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
                    "EmailAddress(id=%s)."
                ),
                request.user.id,
                email.id,
            )
        else:
            logger.warning(
                "User(id=%s) asked to resend email change letter, but no "
                "pending address was found.",
                request.user.id,
            )
            messages.info(
                request,
                "There is no pending email change to re-send a confirmation for.",
            )
        return redirect("email-change")


class EmailChangeCancelView(LoginRequiredMixin, View):
    def post(self, request) -> HttpResponseRedirect:
        email = get_pending_email_address(request.user)
        if email:
            email.delete()
            logger.info(
                "User(id=%s) cancelled pending email change; "
                "EmailAddress(id=%s, user_id=%s) deleted.",
                request.user.id,
                email.id,
                email.user_id,
            )
            messages.info(request, "Email change cancelled.")
        else:
            logger.warning(
                "User(id=%s) attempted to cancel email change, but no pending "
                "EmailAddress was found.",
                request.user.id,
            )
            messages.info(request, "No pending email change to cancel.")
        return redirect("email-change")


class EmailChangeConfirmationView(LoginRequiredMixin, FormView):
    template_name = "users/email_change_confirm.html"
    form_class = EmailChangeConfirmationForm
    success_url = reverse_lazy("email-change")

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["initial"]["token"] = self.kwargs.get("token")
        return kwargs

    def form_valid(self, form) -> HttpResponse:
        change_email_address(self.request.user.id)
        messages.success(self.request, "Your email address was changed successfully.")
        return super().form_valid(form)
