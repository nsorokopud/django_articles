import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from users.models import USER_EMAIL_UNIQUE_CONSTRAINT_NAME, PendingEmailChange, User
from users.settings import PENDING_EMAIL_CHANGE_TTL

from .tokens import email_change_token_generator


logger = logging.getLogger(__name__)


@transaction.atomic
def create_pending_email_change(*, user_id: int, email: str) -> PendingEmailChange:
    delete_expired_pending_email_changes()

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

    if PendingEmailChange.objects.filter(email__iexact=email).exists():
        raise ValidationError("That email address is currently pending confirmation.")

    try:
        pending_email_change = PendingEmailChange.objects.create(user=user, email=email)
    except IntegrityError as e:
        raise ValidationError(
            "This email is already in use or pending confirmation."
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

    if (
        PendingEmailChange.objects.exclude(pk=pending_email_change.pk)
        .filter(email__iexact=new_email)
        .exists()
    ):
        raise ValidationError("This email address is currently pending confirmation.")

    try:
        user.email = new_email
        user.save(update_fields=["email"])
        pending_email_change.delete()
    except IntegrityError as e:
        if _is_user_email_unique_violation(e):
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


def delete_expired_pending_email_changes() -> int:
    cutoff = timezone.now() - PENDING_EMAIL_CHANGE_TTL

    deleted_count, _ = PendingEmailChange.objects.filter(
        created_at__lte=cutoff
    ).delete()

    if deleted_count:
        logger.info("Deleted %d expired pending email changes.", deleted_count)

    return deleted_count


def is_pending_email_change_expired(pending_email_change: PendingEmailChange) -> bool:
    return pending_email_change.created_at <= timezone.now() - PENDING_EMAIL_CHANGE_TTL


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


def _is_user_email_unique_violation(exc: IntegrityError) -> bool:
    diagnostics = getattr(exc.__cause__, "diag", None)
    constraint_name = getattr(diagnostics, "constraint_name", None)
    return constraint_name == USER_EMAIL_UNIQUE_CONSTRAINT_NAME
