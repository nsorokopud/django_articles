from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "users/registration.html"
    success_url = reverse_lazy("login")
