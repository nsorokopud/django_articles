from allauth.account.views import PasswordSetView as AllauthPasswordSetView
from allauth.account.views import (
    sensitive_post_parameters_m,
)
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import CreateView

from users.forms import (
    AuthenticationForm,
    ProfileUpdateForm,
    UserCreationForm,
    UserUpdateForm,
)

from .models import User
from .services import (
    activate_user,
    deactivate_user,
    get_all_supscriptions_of_user,
    get_user_by_id,
    get_user_by_username,
    send_account_activation_email,
    toggle_user_supscription,
)
from .tokens import activation_token_generator


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


class PasswordSetView(AllauthPasswordSetView):
    template_name = "users/password_set.html"

    @sensitive_post_parameters_m
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.has_usable_password():
            raise PermissionDenied
        return View.dispatch(self, request, *args, **kwargs)


class UserLoginView(LoginView):
    form_class = AuthenticationForm
    template_name = "users/login.html"


class UserProfileView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login")

    def get(self, request):
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)
        subscribed_authors = get_all_supscriptions_of_user(request.user)

        context = {
            "user_form": user_form,
            "profile_form": profile_form,
            "subscribed_authors": subscribed_authors,
        }
        return render(request, "users/profile.html", context)

    def post(self, request):
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=request.user.profile
        )

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect(reverse("user-profile"))


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
