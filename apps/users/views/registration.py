import logging
from typing import Optional

from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import CreateView

from config.settings import LOGIN_URL
from users.forms import UserCreationForm

from ..models import User
from ..services import activate_user, deactivate_user, send_account_activation_email
from ..services.tokens import activation_token_generator


logger = logging.getLogger("default_logger")


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "users/registration.html"
    success_url = reverse_lazy("post-registration")

    def form_valid(self, form) -> HttpResponseRedirect:
        user = form.save()
        deactivate_user(user)
        send_account_activation_email(self.request, user)
        return redirect(self.success_url)


class PostUserRegistrationView(View):
    def get(self, request) -> HttpResponse:
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
