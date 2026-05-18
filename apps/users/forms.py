from django import forms
from django.contrib.auth.forms import AuthenticationForm as DefaultAuthenticationForm
from django.contrib.auth.forms import UserCreationForm as DefaultUserCreationForm
from hcaptcha_field import hCaptchaField

from core.validators import validate_uploaded_image
from users.models import PendingEmailChange, Profile, User

from .services.tokens import email_change_token_generator


class AuthenticationForm(DefaultAuthenticationForm):
    username = forms.CharField(label="Username or Email")
    hcaptcha = hCaptchaField(label="")


class UserCreationForm(DefaultUserCreationForm):
    hcaptcha = hCaptchaField(label="")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")

        if PendingEmailChange.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "That email address is currently pending confirmation."
            )

        return email


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
    image = forms.ImageField(
        required=False, validators=[validate_uploaded_image], widget=forms.FileInput()
    )

    class Meta:
        model = Profile
        fields = ["image", "notification_emails_allowed"]
        labels = {"notification_emails_allowed": "Allow notifications via email"}


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(label="Change to:")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        new_email = self.cleaned_data["new_email"].strip().lower()

        if not self.user or not self.user.is_authenticated:
            return new_email

        if (self.user.email or "").strip().lower() == new_email:
            raise forms.ValidationError("Enter a different email address.")

        if (
            User.objects.exclude(pk=self.user.pk)
            .filter(email__iexact=new_email)
            .exists()
        ):
            raise forms.ValidationError("A user with that email already exists.")

        if (
            PendingEmailChange.objects.filter(email__iexact=new_email)
            .exclude(user=self.user)
            .exists()
        ):
            raise forms.ValidationError(
                "That email address is currently pending confirmation."
            )
        return new_email

    def clean(self):
        cleaned_data = super().clean()

        if not self.user or not self.user.is_authenticated:
            raise forms.ValidationError("You must be logged in to change email.")

        if PendingEmailChange.objects.filter(user=self.user).exists():
            raise forms.ValidationError(
                (
                    "There is an unfinished email address change process. "
                    "Cancel it to start a new one."
                )
            )
        return cleaned_data


class EmailChangeConfirmationForm(forms.Form):
    token = forms.CharField(label="Token", widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.pending_email_change_id = kwargs.pop("pending_email_change_id", None)
        self.pending_email_change = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        if self.user is None or not self.user.is_authenticated:
            raise forms.ValidationError(
                "You must be logged in to change the email address."
            )

        try:
            pending_email_change = PendingEmailChange.objects.get(
                id=self.pending_email_change_id, user=self.user
            )
        except PendingEmailChange.DoesNotExist as e:
            raise forms.ValidationError(
                "This email change request no longer exists."
            ) from e

        token = cleaned_data.get("token")
        if not email_change_token_generator.check_token(self.user, token):
            raise forms.ValidationError("Invalid token.")

        self.pending_email_change = pending_email_change
        return cleaned_data
