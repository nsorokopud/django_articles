import logging

from allauth.account.views import PasswordChangeView as AllauthPasswordChangeView
from allauth.account.views import PasswordSetView as AllauthPasswordSetView
from allauth.account.views import sensitive_post_parameters_m
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import CreateView, FormView

from users.forms import (
    AuthenticationForm,
    EmailChangeConfirmationForm,
    EmailChangeForm,
    ProfileUpdateForm,
    UserCreationForm,
    UserUpdateForm,
)

from .models import User
from .services import (
    activate_user,
    change_email_address,
    create_pending_email_address,
    deactivate_user,
    get_all_supscriptions_of_user,
    get_pending_email_address,
    get_user_by_id,
    get_user_by_username,
    send_account_activation_email,
    send_email_change_link,
    toggle_user_supscription,
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
            user = form.save(commit=False)
            deactivate_user(user)
            send_account_activation_email(request, user)
            return redirect(reverse("post-registration"))
        return render(request, self.template_name, {"form": form})


class PostUserRegistrationView(View):
    def get(self, request):
        return render(request, "users/post_registration.html")


class AccountActivationView(View):
    def get(self, request, user_id_b64: str, token: str):
        if request.user.is_authenticated:
            logout(request)
        try:
            user_id = force_str(urlsafe_base64_decode(user_id_b64))
            user = get_user_by_id(user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            context = {
                "is_activation_successful": False,
                "error_message": "Invalid user id",
            }
            return render(request, "users/account_activation.html", context)
        if user.is_active:
            context = {
                "is_activation_successful": False,
                "error_message": "This account is already activated",
            }
            return render(request, "users/account_activation.html", context)
        if not activation_token_generator.check_token(user, token):
            context = {
                "is_activation_successful": False,
                "error_message": "Invalid token",
            }
            return render(request, "users/account_activation.html", context)
        activate_user(user)
        context = {"is_activation_successful": True}
        return render(request, "users/account_activation.html", context)


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
    def post(self, request):
        email = get_pending_email_address(request.user)
        if email:
            send_email_change_link(request, email.email)
            messages.info(
                self.request,
                (
                    "Email change confirmation re-sent. "
                    "Please check your new email address."
                ),
            )
            logger.info(
                "User(id=%s) requested a resend of the email change letter.",
                request.user.id,
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
    def post(self, request):
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

    def get(self, request):
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)
        subscribed_authors = get_all_supscriptions_of_user(request.user)

        context = {
            "user_form": user_form,
            "profile_form": profile_form,
            "subscribed_authors": subscribed_authors,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=request.user.profile
        )
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect(reverse("user-profile"))
        context = {
            "user_form": user_form,
            "profile_form": profile_form,
            "subscribed_authors": get_all_supscriptions_of_user(request.user),
        }
        return render(request, self.template_name, context)


class AuthorPageView(View):
    def get(self, request, author_username):
        author = get_user_by_username(author_username)
        context = {
            "author": author,
            "author_image_url": author.profile.image.url,
            "subscribers_count": author.profile.subscribers.count(),
            "is_subscribed": request.user in author.profile.subscribers.all(),
        }
        return render(request, "users/author_page.html", context)


class AuthorSubscribeView(LoginRequiredMixin, View):
    def post(self, request, author_username):
        author = get_user_by_username(author_username)
        toggle_user_supscription(request.user, author)
        return redirect(reverse("author-page", args=(author_username,)))
