from django.core.exceptions import PermissionDenied
from django.core.validators import validate_email
from django.http import HttpRequest
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.services.email import EmailConfig
from core.tasks import send_email_task

from ..models import User
from .tokens import activation_token_generator, email_change_token_generator


def send_account_activation_email(request: HttpRequest, user: User):
    encoded_user_id = urlsafe_base64_encode(force_bytes(user.pk))
    token = activation_token_generator.make_token(user)
    url = request.build_absolute_uri(
        reverse("account-activate", args=[encoded_user_id, token])
    )

    email_config = EmailConfig(
        recipients=[user.email],
        subject="User account activation",
        text_template="users/emails/activation_email.txt",
        html_template="users/emails/activation_email.html",
        context={"username": request.user.get_username(), "url": url},
    )
    send_email_task.delay(email_config)


def send_email_change_link(request: HttpRequest, new_email: str) -> None:
    if not request.user.is_authenticated:
        raise PermissionDenied("Login required to change email address.")

    validate_email(new_email)

    token = email_change_token_generator.make_token(request.user)
    url = request.build_absolute_uri(reverse("email-change-confirm", args=[token]))

    email_config = EmailConfig(
        recipients=[new_email],
        subject="Confirm email change",
        text_template="users/emails/email_change.txt",
        html_template="users/emails/email_change.html",
        context={"username": request.user.get_username(), "url": url},
    )
    send_email_task.delay(email_config)
