import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from core.db import get_constraint_name
from users.models import (
    USER_EMAIL_UNIQUE_CONSTRAINT_NAME,
    PendingEmailChange,
    User,
)

from ..normalization import normalize_email
from .sessions import invalidate_user_sessions
from .tokens import email_change_token_generator


logger = logging.getLogger(__name__)


@transaction.atomic
def create_pending_email_change(*, user_id: int, email: str) -> PendingEmailChange:
    email = normalize_email(email)

    if not email:
        raise ValidationError("Email is required.")

    validate_email(email)

    user = User.objects.select_for_update().get(pk=user_id)

    if PendingEmailChange.objects.filter(user=user).exists():
        raise ValidationError("There is already a pending email change.")

    if normalize_email(user.email) == email:
        raise ValidationError("Enter a different email address.")

    if User.objects.exclude(pk=user_id).filter(email__iexact=email).exists():
        raise ValidationError("A user with that email already exists.")

    pending_email_change = PendingEmailChange.objects.create(user=user, email=email)

    logger.info(
        "PendingEmailChange(id=%s, user_id=%s) was created.",
        pending_email_change.id,
        pending_email_change.user_id,
    )
    return pending_email_change


def delete_pending_email_change(user: User) -> None:
    deleted_count, _ = PendingEmailChange.objects.filter(user=user).delete()

    if deleted_count:
        logger.info("Pending email change for User(id=%s) was removed.", user.id)
    else:
        logger.warning(
            "Attempted to remove non-existent PendingEmailChange for User(id=%s).",
            user.id,
        )


@transaction.atomic
def change_email_address(
    *, user_id: int, pending_email_change_id: int, token: str
) -> None:
    logger.info("Attempting to change email address for User(id=%s).", user_id)

    user = User.objects.select_for_update().get(id=user_id)

    try:
        pending_email_change = PendingEmailChange.objects.select_for_update().get(
            id=pending_email_change_id, user_id=user_id
        )
    except PendingEmailChange.DoesNotExist as e:
        raise ValidationError("This email change request no longer exists.") from e

    if is_pending_email_change_expired(pending_email_change):
        raise ValidationError("This email change link has expired.")

    if not email_change_token_generator.check_token(user, token):
        raise ValidationError("Invalid email change link.")

    new_email = normalize_email(pending_email_change.email)
    old_email = normalize_email(user.email)

    validate_email(new_email)

    if old_email == new_email:
        pending_email_change.delete()
        _delete_allauth_email_addresses_for_user(user_id)
        logger.info(
            "Deleted stale same-email PendingEmailChange(id=%s, user_id=%s).",
            pending_email_change_id,
            user_id,
        )
        return

    if User.objects.exclude(pk=user_id).filter(email__iexact=new_email).exists():
        raise ValidationError("This email address is no longer available.")

    try:
        user.email = new_email
        user.save(update_fields=["email"])
        pending_email_change.delete()
        invalidate_user_sessions(user_id=user.id)
    except IntegrityError as e:
        if get_constraint_name(e) == USER_EMAIL_UNIQUE_CONSTRAINT_NAME:
            raise ValidationError("This email address is no longer available.") from e
        raise

    _delete_allauth_email_addresses_for_user(user_id)
    delete_social_accounts_with_email(user_id=user_id, email=old_email)

    logger.info(
        "User(id=%s) changed email from %s to %s.", user_id, old_email, new_email
    )


def delete_social_accounts_with_email(*, user_id: int, email: str) -> None:
    if not connection.in_atomic_block:
        raise transaction.TransactionManagementError(
            "This function must be called inside an atomic transaction."
        )

    normalized_email = normalize_email(email)

    accounts = SocialAccount.objects.select_for_update().filter(user_id=user_id)

    count = 0
    for account in accounts:
        account_email = normalize_email(account.extra_data.get("email"))

        if account_email != normalized_email:
            continue

        account.delete()
        logger.info("SocialAccount(id=%s) was removed.", account.id)
        count += 1

    logger.info(
        "Deleted %d social accounts for User(id=%s) with email %s.",
        count,
        user_id,
        normalized_email,
    )


def delete_expired_pending_email_changes() -> int:
    return _delete_expired_pending_email_changes()


def is_pending_email_change_expired(pending_email_change: PendingEmailChange) -> bool:
    return (
        pending_email_change.created_at
        <= timezone.now() - settings.USERS_PENDING_EMAIL_CHANGE_TTL
    )


def _delete_allauth_email_addresses_for_user(user_id: int) -> None:
    if not connection.in_atomic_block:
        raise transaction.TransactionManagementError(
            "This function must be called inside an atomic transaction."
        )

    deleted_count, _ = (
        EmailAddress.objects.select_for_update().filter(user_id=user_id).delete()
    )

    logger.info(
        "Deleted %d allauth EmailAddress rows for User(id=%s).", deleted_count, user_id
    )


def _delete_expired_pending_email_changes() -> int:
    cutoff = timezone.now() - settings.USERS_PENDING_EMAIL_CHANGE_TTL

    queryset = PendingEmailChange.objects.filter(created_at__lte=cutoff)

    deleted_count, _ = queryset.delete()

    if deleted_count:
        logger.info(
            "Deleted %d expired pending email change%s.",
            deleted_count,
            "" if deleted_count == 1 else "s",
        )

    return deleted_count
