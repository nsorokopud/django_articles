import logging

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from core.db import get_constraint_name
from users.models import (
    USER_EMAIL_UNIQUE_CONSTRAINT_NAME,
    USER_USERNAME_UNIQUE_CONSTRAINT_NAME,
    PendingEmailChange,
    User,
)

from ..normalization import normalize_email, normalize_username
from ..validators import validate_username_is_not_email
from .email_addresses import delete_expired_pending_email_changes_for_email


logger = logging.getLogger(__name__)


def register_user(*, username: str, email: str, password: str) -> User:
    username = normalize_username(username)
    email = normalize_email(email)

    if not username:
        raise ValidationError({"username": "Username is required."})

    validate_username_is_not_email(username)

    if not email:
        raise ValidationError({"email": "Email is required."})

    validate_email(email)

    try:
        with transaction.atomic():
            delete_expired_pending_email_changes_for_email(email=email)

            _validate_registration_availability(username=username, email=email)

            return User.objects.create_user(
                username=username, email=email, password=password, is_active=False
            )

    except IntegrityError as e:
        constraint_name = get_constraint_name(e)

        if constraint_name == USER_EMAIL_UNIQUE_CONSTRAINT_NAME:
            raise ValidationError(
                {"email": "A user with that email already exists."}
            ) from e

        if constraint_name == USER_USERNAME_UNIQUE_CONSTRAINT_NAME:
            raise ValidationError(
                {"username": "A user with that username already exists."}
            ) from e

        try:
            _validate_registration_availability(username=username, email=email)
        except ValidationError as validation_error:
            raise validation_error from e

        raise


@transaction.atomic
def activate_user(user: User) -> None:
    user = User.objects.select_for_update().get(pk=user.pk)

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])

        _delete_conflicting_pending_email_changes_for_activated_user(user)

        logger.info("User %s was activated.", user.id)
    else:
        logger.info("User %s was already active.", user.id)


def _validate_registration_availability(*, username: str, email: str) -> None:
    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError({"username": "A user with that username already exists."})

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "A user with that email already exists."})


def _delete_conflicting_pending_email_changes_for_activated_user(user: User) -> None:
    email = normalize_email(user.email)
    if not email:
        return

    deleted_count, _ = (
        PendingEmailChange.objects.filter(email__iexact=email)
        .exclude(user_id=user.id)
        .delete()
    )

    if deleted_count:
        logger.info(
            "Deleted %d conflicting pending email change%s for activated User(id=%s).",
            deleted_count,
            "" if deleted_count == 1 else "s",
            user.id,
        )
