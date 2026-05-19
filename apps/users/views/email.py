import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from users.forms import EmailChangeConfirmationForm, EmailChangeForm

from ..selectors import get_pending_email_change
from ..services import change_email_address, send_email_change_link
from ..services.email_addresses import (
    create_pending_email_change,
    delete_pending_email_change,
)


logger = logging.getLogger(__name__)


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


class EmailChangeConfirmationView(LoginRequiredMixin, FormView):
    template_name = "users/email_change_confirm.html"
    form_class = EmailChangeConfirmationForm
    success_url = reverse_lazy("email-change")

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["pending_email_change_id"] = self.kwargs.get("pending_email_change_id")
        kwargs["token"] = self.kwargs.get("token")
        return kwargs

    def form_valid(self, form) -> HttpResponse:
        try:
            change_email_address(
                user_id=self.request.user.id,
                pending_email_change_id=form.pending_email_change.id,
            )
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

        messages.success(self.request, "Your email address was changed successfully.")
        return super().form_valid(form)
