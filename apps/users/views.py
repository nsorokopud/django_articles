import logging
from typing import Any, Optional

from allauth.account.views import PasswordChangeView as AllauthPasswordChangeView
from allauth.account.views import PasswordSetView as AllauthPasswordSetView
from allauth.account.views import sensitive_post_parameters_m
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import CreateView, FormView, TemplateView

from config.settings import LOGIN_URL
from users.forms import (
    AuthenticationForm,
    EmailChangeConfirmationForm,
    EmailChangeForm,
    ProfileUpdateForm,
    UserCreationForm,
    UserUpdateForm,
)

from .cache import get_cached_subscribers_count
from .models import User
from .selectors import (
    get_all_subscriptions_of_user,
    get_author_with_viewer_subscription_status,
    get_pending_email_address,
)
from .services import (
    activate_user,
    change_email_address,
    create_pending_email_address,
    deactivate_user,
    send_account_activation_email,
    send_email_change_link,
    toggle_user_subscription,
)
from .services.tokens import activation_token_generator, password_reset_token_generator


logger = logging.getLogger("default_logger")


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "users/registration.html"
    success_url = reverse_lazy("login")

    def post(self, request):
        form = self.get_form()
        if form.is_valid():
            user = form.save()
            deactivate_user(user)
            send_account_activation_email(request, user)
            return redirect(reverse("post-registration"))
        return render(request, self.template_name, {"form": form})


class PostUserRegistrationView(View):
    def get(self, request):
        return render(request, "users/post_registration.html")


class AccountActivationView(View):
    template_name = "users/account_activation.html"
    expired_link_message = "The activation link is invalid or has expired"

    def get(self, request, user_id_b64: str, token: str) -> HttpResponse:
        user = self._get_user_from_b64(user_id_b64)
        if user is None:
            return self._render_failure(self.expired_link_message)

        if user.is_active:
            messages.info(request, "Your account is already activated.")
            return redirect(reverse("login"))

        if not activation_token_generator.check_token(user, token):
            logger.warning(
                "Account activation attempt with invalid token for user_id_b64=%s.",
                user_id_b64,
            )
            return self._render_failure(self.expired_link_message)

        activate_user(user)
        if request.user.is_authenticated:
            logout(request)
        logger.info("User %s activated their account via link", user.id)
        messages.success(self.request, "Your account was successfully activated.")
        return redirect(LOGIN_URL)

    def _get_user_from_b64(self, user_id_b64: str) -> Optional[User]:
        try:
            user_id = force_str(urlsafe_base64_decode(user_id_b64))
            return get_object_or_404(User, pk=user_id)
        except (TypeError, ValueError, OverflowError):
            logger.warning("Invalid base64 user ID (%s).", user_id_b64)
            return None

    def _render_failure(self, message: str) -> HttpResponse:
        context = {
            "is_activation_successful": False,
            "error_message": message,
        }
        return render(self.request, self.template_name, context, status=400)


class PasswordChangeView(AllauthPasswordChangeView):
    template_name = "users/password_change.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info("Password changed for User(id=%s).", self.request.user.pk)
        return response


class PasswordSetView(AllauthPasswordSetView):
    template_name = "users/password_set.html"

    @sensitive_post_parameters_m
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.has_usable_password():
            raise PermissionDenied
        return View.dispatch(self, request, *args, **kwargs)


class PasswordResetView(DjangoPasswordResetView):
    template_name = "users/password_reset.html"
    token_generator = password_reset_token_generator
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        messages.success(
            self.request, "We've emailed you a link to reset your password."
        )
        return super().form_valid(form)


class UserPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "users/password_reset_confirm.html"
    token_generator = password_reset_token_generator
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        messages.success(self.request, "Your password was reset successfully.")
        return super().form_valid(form)


class EmailChangeView(LoginRequiredMixin, FormView):
    template_name = "users/email_change.html"
    form_class = EmailChangeForm
    success_url = reverse_lazy("email-change")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_email"] = get_pending_email_address(self.request.user)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        new_email = create_pending_email_address(
            self.request.user, form.cleaned_data["new_email"]
        )
        send_email_change_link(self.request, new_email.email)
        messages.success(
            self.request,
            "Email change confirmation sent. Please check your new email address.",
        )
        return super().form_valid(form)


class EmailChangeResendView(LoginRequiredMixin, View):
    def post(self, request) -> HttpResponseRedirect:
        email = get_pending_email_address(request.user)
        if email:
            send_email_change_link(request, email.email)
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["initial"]["token"] = self.kwargs.get("token")
        return kwargs

    def form_valid(self, form):
        change_email_address(self.request.user.id)
        messages.success(self.request, "Your email address was changed successfully.")
        return super().form_valid(form)


class UserLoginView(LoginView):
    form_class = AuthenticationForm
    template_name = "users/login.html"


class UserProfileView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login")
    template_name = "users/profile.html"

    def get(self, request) -> HttpResponse:
        context = self.get_context_data()
        return render(request, self.template_name, context)

    def post(self, request) -> HttpResponse | HttpResponseRedirect:
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=request.user.profile
        )
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect(request.path)

        context = self.get_context_data(user_form=user_form, profile_form=profile_form)
        return render(request, self.template_name, context)

    def get_context_data(self, user_form=None, profile_form=None) -> dict[str, Any]:
        return {
            "user_form": user_form or UserUpdateForm(instance=self.request.user),
            "profile_form": profile_form
            or ProfileUpdateForm(instance=self.request.user.profile),
            "subscribed_authors": get_all_subscriptions_of_user(self.request.user),
        }


class AuthorPageView(TemplateView):
    template_name = "users/author_page.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        author = get_author_with_viewer_subscription_status(
            self.kwargs.get("author_id"), self.request.user
        )
        subscribers_count = get_cached_subscribers_count(author)

        user = self.request.user
        context["author"] = author
        context["author_image_url"] = author.profile.image.url
        context["subscribers_count"] = subscribers_count
        context["is_viewer_subscribed"] = (
            author.is_subscribed_by_viewer if user.is_authenticated else False
        )
        return context


class AuthorSubscribeView(LoginRequiredMixin, View):
    def post(self, request, author_id: int) -> HttpResponseRedirect:
        author = get_object_or_404(User, pk=author_id)

        if request.user == author:
            messages.error(
                request, "You cannot subscribe to or unsubscribe from yourself."
            )
            return redirect("author-page", author_id=author.id)

        try:
            subscribed = toggle_user_subscription(request.user, author)
            message = (
                f"You are now subscribed to {author.username}."
                if subscribed
                else f"You unsubscribed from {author.username}."
            )
            messages.success(request, message)
        except ValidationError:
            logger.exception(
                "Error while toggling subscription of user %s to author %s",
                request.user.username,
                author.username,
            )
            messages.error(
                request, "Something went wrong while managing your subscription."
            )
        return redirect("author-page", author_id=author_id)
