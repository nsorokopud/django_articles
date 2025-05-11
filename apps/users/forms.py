from allauth.account.models import EmailAddress
from django import forms
from django.contrib.auth.forms import AuthenticationForm as DefaultAuthenticationForm
from django.contrib.auth.forms import UserCreationForm as DefaultUserCreationForm
from hcaptcha_field import hCaptchaField

from users.models import Profile, User

from .services import enforce_unique_email_type_per_user, get_pending_email_address
from .services.tokens import email_change_token_generator


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


class EmailAddressModelForm(forms.ModelForm):
    class Meta:
        model = EmailAddress
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        user = cleaned_data.get("user")
        if not user:
            raise forms.ValidationError("User is required.")

        for field_name, value in cleaned_data.items():
            setattr(self.instance, field_name, value)

        enforce_unique_email_type_per_user(self.instance)
        return cleaned_data


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(label="Change to:")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        new_email = self.cleaned_data["new_email"]
        if self.user.email == new_email:
            raise forms.ValidationError("Enter a different email address.")
        if User.objects.exclude(pk=self.user.pk).filter(email=new_email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return new_email

    def clean(self):
        cleaned_data = super().clean()

        new_email = cleaned_data.get("new_email")
        if not new_email:
            return cleaned_data

        email_instance = EmailAddress(
            user=self.user, email=new_email, verified=False, primary=False
        )
        try:
            enforce_unique_email_type_per_user(email_instance)
        except forms.ValidationError as e:
            raise forms.ValidationError(
                (
                    "There is an unfinished email address change process. "
                    "Cancel it to start a new one."
                )
            ) from e
        return cleaned_data


class EmailChangeConfirmationForm(forms.Form):
    token = forms.CharField(label="Token", widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        if self.user is None:
            raise forms.ValidationError(
                "You must be logged in to change the email address."
            )

        email = get_pending_email_address(self.user)
        if email is None:
            raise forms.ValidationError("You don't have any pending email addresses.")

        token = cleaned_data.get("token")
        if not email_change_token_generator.check_token(self.user, token):
            raise forms.ValidationError("Invalid token.")

        return cleaned_data
