import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, connection, transaction

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

    if EmailAddress.objects.filter(user=user, primary=False).exists():
        raise ValidationError("There is already a pending email change.")

    if (user.email or "").strip().lower() == email:
        raise ValidationError("Enter a different email address.")

    email_address = EmailAddress(user=user, email=email, primary=False, verified=False)

    enforce_single_current_and_pending_email_per_user(email_address)
    try:
        email_address.save()
    except IntegrityError as e:
        raise ValidationError(
            "This email is already in use or you already have a pending email change."
        ) from e

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
    logger.info("Attempting to change email address for User(id=%s)", user_id)

    user = User.objects.select_for_update().get(id=user_id)

    email_addresses = list(
        EmailAddress.objects.select_for_update().filter(user=user).order_by("id")
    )

    primary_emails = [email for email in email_addresses if email.primary]
    pending_emails = [email for email in email_addresses if not email.primary]

    if len(primary_emails) != 1:
        raise ValidationError("Expected exactly one primary email address.")

    if len(pending_emails) != 1:
        raise ValidationError("Expected exactly one pending email change.")

    old_email = primary_emails[0]
    new_email = pending_emails[0]

    normalized_new_email = new_email.email.strip().lower()
    old_email_value = old_email.email.strip().lower()

    validate_email(normalized_new_email)

    old_email_id = old_email.id
    new_email_id = new_email.id

    try:
        EmailAddress.objects.filter(pk=old_email_id).delete()

        updated = EmailAddress.objects.filter(pk=new_email_id).update(
            email=normalized_new_email,
            verified=True,
            primary=True,
        )

        if updated != 1:
            raise ValidationError("Pending email address no longer exists.")

        user.email = normalized_new_email
        user.save(update_fields=["email"])

    except IntegrityError as e:
        raise ValidationError("This email address is no longer available.") from e

    delete_social_accounts_with_email(user_id=user_id, email=old_email_value)

    logger.info(
        "User(id=%s) changed email from EmailAddress(id=%s) to EmailAddress(id=%s)",
        user_id,
        old_email_id,
        new_email_id,
    )


@transaction.atomic
def sync_primary_email_address_for_user(*, user_id: int) -> EmailAddress:
    """Ensure User.email has exactly one matching verified primary EmailAddress.

    User.email is the source of truth. Any other EmailAddress rows for the user
    are stale and are removed.
    """
    user = User.objects.select_for_update().get(pk=user_id)
    email = (user.email or "").strip().lower()

    if not email:
        raise ValidationError("User email is required.")

    validate_email(email)

    if user.email != email:
        user.email = email
        user.save(update_fields=["email"])

    email_addresses = list(
        EmailAddress.objects.select_for_update().filter(user_id=user.id).order_by("id")
    )

    matching_email_address = next(
        (
            email_address
            for email_address in email_addresses
            if (email_address.email or "").strip().lower() == email
        ),
        None,
    )

    if matching_email_address is None:
        EmailAddress.objects.filter(user_id=user.id).delete()

        return EmailAddress.objects.create(
            user_id=user.id, email=email, verified=True, primary=True
        )

    EmailAddress.objects.filter(user_id=user.id).exclude(
        pk=matching_email_address.pk
    ).delete()

    EmailAddress.objects.filter(pk=matching_email_address.pk).update(
        email=email, verified=True, primary=True
    )

    matching_email_address.refresh_from_db()
    return matching_email_address


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
        "Deleted %d social accounts for User(id=%s) with email %s",
        count,
        user_id,
        normalized_email,
    )
