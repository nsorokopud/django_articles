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

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["image", "notification_emails_allowed"]
        labels = {"notification_emails_allowed": "Allow notifications via email"}
        widgets = {
            "image": forms.FileInput(),
        }
