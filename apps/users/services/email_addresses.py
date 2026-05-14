import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import connection, transaction

from users.models import User

from ..selectors import get_pending_email_address


logger = logging.getLogger(__name__)


def enforce_single_current_and_pending_email_per_user(instance: EmailAddress) -> None:
    """Enforces the following model:
    - at most one primary EmailAddress per user, representing the current email
    - at most one non-primary EmailAddress per user, representing a pending email change
    - no email address may be used by another user or another user's EmailAddress
    """
    if instance.email:
        instance.email = instance.email.strip().lower()

    queryset = EmailAddress.objects.filter(user=instance.user, primary=instance.primary)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    if queryset.exists():
        address_type = "primary" if instance.primary else "pending"
        raise ValidationError(f"This user already has a {address_type} email address.")

    if instance.email:
        existing_user_email = (
            User.objects.exclude(pk=instance.user_id)
            .filter(email__iexact=instance.email)
            .exists()
        )
        if existing_user_email:
            raise ValidationError("A user with that email already exists.")

        existing_email_address = (
            EmailAddress.objects.exclude(user_id=instance.user_id)
            .filter(email__iexact=instance.email)
            .exists()
        )
        if existing_email_address:
            raise ValidationError("A user with that email already exists.")


@transaction.atomic
def create_pending_email_address(*, user_id: int, email: str) -> EmailAddress:
    user = User.objects.select_for_update().get(pk=user_id)
    email = email.strip().lower()

    if not email:
        raise ValidationError("Email is required.")

    validate_email(email)

    if EmailAddress.objects.filter(user=user, primary=False, verified=False).exists():
        raise ValidationError("There is already a pending email change.")

    if (user.email or "").strip().lower() == email:
        raise ValidationError("Enter a different email address.")

    email_address = EmailAddress(user=user, email=email, primary=False, verified=False)

    enforce_single_current_and_pending_email_per_user(email_address)
    email_address.save()

    logger.info(
        "Pending EmailAddress(id=%s, user_id=%s) was created.",
        email_address.id,
        email_address.user_id,
    )
    return email_address


def delete_pending_email_address(user: User) -> None:
    email = get_pending_email_address(user)
    if email:
        email.delete()
        logger.info(
            "Pending EmailAddress(id=%s, user_id=%s) was removed.",
            email.id,
            user.id,
        )
    else:
        logger.warning(
            "Attempt of removing non-existent EmailAddress for User(id=%s)", user.id
        )


@transaction.atomic
def change_email_address(user_id: int) -> None:
    """Replaces user's email address with the pending one: verifies it,
    makes it primary, updates user.email, deletes the old address and
    all social accounts associated with it.
    """
    logger.info("Attempting to change email address for User(id=%s)", user_id)

    user = User.objects.select_for_update().get(id=user_id)
    new_email = EmailAddress.objects.select_for_update().get(
        user=user, primary=False, verified=False
    )
    old_email = EmailAddress.objects.select_for_update().get(user=user, primary=True)
    user.email = new_email.email.strip().lower()
    user.save(update_fields=["email"])

    # Bypass pre-save signal that enforces email validation
    EmailAddress.objects.filter(id=old_email.id).update(primary=False)
    EmailAddress.objects.filter(id=new_email.id).update(primary=True, verified=True)

    old_email.delete()
    logger.info("EmailAddress(id=%s) was deleted.", old_email.id)
    delete_social_accounts_with_email(old_email.email.strip().lower())
    logger.info(
        "User(id=%s) changed email from (id=%s) to (id=%s)",
        user_id,
        old_email.id,
        new_email.id,
    )


@transaction.atomic
def sync_primary_email_address_for_user(*, user_id: int) -> EmailAddress:
    """Ensures User.email has one matching verified primary EmailAddress"""
    user = User.objects.select_for_update().get(pk=user_id)
    email = (user.email or "").strip().lower()

    if not email:
        raise ValidationError("User email is required.")

    validate_email(email)

    if user.email != email:
        user.email = email
        user.save(update_fields=["email"])

    email_addresses = list(
        EmailAddress.objects.select_for_update().filter(user_id=user.id)
    )

    matching_email_address = next(
        (
            email_address
            for email_address in email_addresses
            if (email_address.email or "").strip().lower() == email
        ),
        None,
    )

    primary_addresses = EmailAddress.objects.filter(user_id=user.id, primary=True)

    if matching_email_address is not None:
        primary_addresses = primary_addresses.exclude(pk=matching_email_address.pk)

    # Bypass EmailAddress pre-save validation while repairing primary state.
    primary_addresses.update(primary=False)

    if matching_email_address is None:
        return EmailAddress.objects.create(
            user_id=user.id, email=email, verified=True, primary=True
        )

    EmailAddress.objects.filter(pk=matching_email_address.pk).update(
        email=email, verified=True, primary=True
    )

    matching_email_address.refresh_from_db()
    return matching_email_address


def delete_social_accounts_with_email(email: str) -> None:
    """Deletes all social accounts with the specified email address.
    Raises TransactionManagementError if called outside of an atomic
    transaction.
    """
    if not connection.in_atomic_block:
        raise transaction.TransactionManagementError(
            "This function must be called inside an atomic transaction."
        )

    accounts = SocialAccount.objects.select_for_update().filter(extra_data__email=email)

    if not accounts.exists():
        logger.info("No social accounts found with email %s", email)
        return

    # One-by-one deletion instead of queryset.delete() to ensure thread
    # safety and to preserve logging for each account
    count = 0
    for account in accounts:
        account.delete()
        logger.info("SocialAccount(id=%s) was removed.", account.id)
        count += 1

    logger.info("Deleted %d social accounts with email %s", count, email)
