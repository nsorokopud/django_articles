from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "users/registration.html"
    success_url = reverse_lazy("login")


class UserLoginView(LoginView):
    template_name = "users/login.html"
