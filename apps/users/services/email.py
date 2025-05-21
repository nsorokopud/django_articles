from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from ..models import User
from .tokens import activation_token_generator, email_change_token_generator


def send_account_activation_email(request: HttpRequest, user: User):
    encoded_user_id = urlsafe_base64_encode(force_bytes(user.pk))
    token = activation_token_generator.make_token(user)
    url = request.build_absolute_uri(
        reverse("account-activate", args=[encoded_user_id, token])
    )

    context = {"username": request.user.get_username(), "url": url}
    html_content = render_to_string("users/emails/activation_email.html", context)
    text_content = render_to_string("users/emails/activation_email.txt", context)

    email = EmailMultiAlternatives(
        subject="User account activation", body=text_content, to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_email_change_link(request: HttpRequest, new_email: str) -> None:
    if not request.user.is_authenticated:
        raise PermissionDenied("Login required to change email address.")

    validate_email(new_email)

    token = email_change_token_generator.make_token(request.user)
    url = request.build_absolute_uri(reverse("email-change-confirm", args=[token]))
    context = {"username": request.user.get_username(), "url": url}
    html_content = render_to_string("users/emails/email_change.html", context)
    text_content = render_to_string("users/emails/email_change.txt", context)

    email = EmailMultiAlternatives(
        subject="Confirm email change", body=text_content, to=[new_email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
