import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, connection, transaction

from users.models import PendingEmailChange, User


logger = logging.getLogger(__name__)


@transaction.atomic
def create_pending_email_change(*, user_id: int, email: str) -> PendingEmailChange:
    user = User.objects.select_for_update().get(pk=user_id)
    email = (email or "").strip().lower()

    if not email:
        raise ValidationError("Email is required.")

    validate_email(email)

    if PendingEmailChange.objects.filter(user=user).exists():
        raise ValidationError("There is already a pending email change.")

    if (user.email or "").strip().lower() == email:
        raise ValidationError("Enter a different email address.")

    if User.objects.exclude(pk=user_id).filter(email__iexact=email).exists():
        raise ValidationError("A user with that email already exists.")

    try:
        pending_email_change = PendingEmailChange.objects.create(user=user, email=email)
    except IntegrityError as e:
        raise ValidationError(
            "This email is already in use or you already have a pending email change."
        ) from e

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
def change_email_address(*, user_id: int, pending_email_change_id: int) -> None:
    logger.info("Attempting to change email address for User(id=%s).", user_id)

    user = User.objects.select_for_update().get(id=user_id)

    try:
        pending_email_change = PendingEmailChange.objects.select_for_update().get(
            id=pending_email_change_id, user_id=user_id
        )
    except PendingEmailChange.DoesNotExist as e:
        raise ValidationError("This email change request no longer exists.") from e

    new_email = pending_email_change.email.strip().lower()
    old_email = (user.email or "").strip().lower()

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
    except IntegrityError as e:
        raise ValidationError("This email address is no longer available.") from e

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

    normalized_email = email.strip().lower()

    accounts = SocialAccount.objects.select_for_update().filter(user_id=user_id)

    count = 0
    for account in accounts:
        account_email = (account.extra_data.get("email") or "").strip().lower()

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
