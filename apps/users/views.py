from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import UserUpdateForm, ProfileUpdateForm
from .services import delete_profile_image


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "users/registration.html"
    success_url = reverse_lazy("login")


class UserLoginView(LoginView):
    template_name = "users/login.html"


class UserLogoutView(LogoutView):
    template_name = "users/logout.html"


class UserProfileView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login")

    def get(self, request):
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

        context = {"user_form": user_form, "profile_form": profile_form}
        return render(request, "users/profile.html", context)

    def post(self, request):
        old_profile_image = request.user.profile.image.path
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=request.user.profile
        )

        if user_form.is_valid() and profile_form.is_valid():
            if request.user.profile.image.path != old_profile_image:
                delete_profile_image(old_profile_image)

            user_form.save()
            profile_form.save()
            return redirect(reverse("user-profile"))
