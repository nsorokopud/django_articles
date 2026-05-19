from django import forms
from django.contrib.auth.forms import AuthenticationForm as DefaultAuthenticationForm
from django.contrib.auth.forms import UserCreationForm as DefaultUserCreationForm
from hcaptcha_field import hCaptchaField

from core.validators import validate_uploaded_image
from users.models import PendingEmailChange, Profile, User

from .services.tokens import email_change_token_generator
from .validators import validate_username_is_not_email


class AuthenticationForm(DefaultAuthenticationForm):
    username = forms.CharField(label="Username or Email")
    hcaptcha = hCaptchaField(label="")


class UserCreationForm(DefaultUserCreationForm):
    hcaptcha = hCaptchaField(label="")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        validate_username_is_not_email(username)
        return username

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username"]

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        validate_username_is_not_email(username)
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
        return self.cleaned_data["new_email"].strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        if not self.user or not self.user.is_authenticated:
            raise forms.ValidationError("You must be logged in to change email.")
        return cleaned_data


class EmailChangeConfirmationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.pending_email_change_id = kwargs.pop("pending_email_change_id", None)
        self.token = kwargs.pop("token", None)
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

        if not email_change_token_generator.check_token(self.user, self.token):
            raise forms.ValidationError("Invalid token.")

        self.pending_email_change = pending_email_change
        return cleaned_data
