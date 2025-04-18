from django import forms
from django.contrib.auth.forms import AuthenticationForm as DefaultAuthenticationForm
from django.contrib.auth.forms import UserCreationForm as DefaultUserCreationForm
from hcaptcha_field import hCaptchaField

from users.models import Profile, User


class AuthenticationForm(DefaultAuthenticationForm):
    username = forms.CharField(label="Username or Email")
    hcaptcha = hCaptchaField(label="")


class UserCreationForm(DefaultUserCreationForm):
    hcaptcha = hCaptchaField(label="")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username"]


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["image"]
