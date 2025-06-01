import logging
from urllib.parse import urljoin

from django.core.validators import validate_email
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.services.email import EmailConfig, mask_email
from core.tasks import send_email_task

from ..models import User
from ..settings import (
    ACTIVATION_EMAIL_HTML_TEMPLATE,
    ACTIVATION_EMAIL_SUBJECT,
    ACTIVATION_EMAIL_TEXT_TEMPLATE,
    EMAIL_CHANGE_HTML_TEMPLATE,
    EMAIL_CHANGE_SUBJECT,
    EMAIL_CHANGE_TEXT_TEMPLATE,
)
from .tokens import activation_token_generator, email_change_token_generator


logger = logging.getLogger("default_logger")


def send_account_activation_email(user: User, base_url: str) -> None:
    encoded_user_id = urlsafe_base64_encode(force_bytes(user.id))
    token = activation_token_generator.make_token(user)
    url = urljoin(base_url, reverse("account-activate", args=[encoded_user_id, token]))

    email_config = EmailConfig(
        recipients=[user.email],
        subject=ACTIVATION_EMAIL_SUBJECT,
        text_template=ACTIVATION_EMAIL_TEXT_TEMPLATE,
        html_template=ACTIVATION_EMAIL_HTML_TEMPLATE,
        context={"username": user.get_username(), "url": url},
    )
    send_email_task.delay(email_config)
    logger.info(
        "Account activation email queued for user %s, email %s",
        user.id,
        mask_email(user.email),
    )


def send_email_change_link(user: User, new_email: str, base_url: str) -> None:
    validate_email(new_email)
    token = email_change_token_generator.make_token(user)
    url = urljoin(base_url, reverse("email-change-confirm", args=[token]))

    email_config = EmailConfig(
        recipients=[new_email],
        subject=EMAIL_CHANGE_SUBJECT,
        text_template=EMAIL_CHANGE_TEXT_TEMPLATE,
        html_template=EMAIL_CHANGE_HTML_TEMPLATE,
        context={"username": user.get_username(), "url": url},
    )
    send_email_task.delay(email_config)
    logger.info(
        "User %s requested email change to %s. Confirmation email queued.",
        user.id,
        mask_email(new_email),
    )
