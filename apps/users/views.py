from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView

from users.forms import (
    AuthenticationForm,
    ProfileUpdateForm,
    UserCreationForm,
    UserUpdateForm,
)
from .services import get_all_supscriptions_of_user, get_user_by_username, toggle_user_supscription


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "users/registration.html"
    success_url = reverse_lazy("login")


class UserLoginView(LoginView):
    form_class = AuthenticationForm
    template_name = "users/login.html"


class UserLogoutView(LogoutView):
    template_name = "users/logout.html"


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
