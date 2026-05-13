import logging

from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.db import transaction

from users.models import User

from ..selectors import get_pending_email_address
from .users import delete_social_accounts_with_email


logger = logging.getLogger(__name__)


def enforce_unique_email_type_per_user(instance: EmailAddress) -> None:
    """Ensures that a user has at most one email address of each type (primary or
    non-primary). Raises `ValidationError` if the user already has an email address with
    the same `primary` value.
    """
    if instance.email:
        instance.email = instance.email.strip().lower()

    queryset = EmailAddress.objects.filter(user=instance.user, primary=instance.primary)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    if queryset.exists():
        address_type = "primary" if instance.primary else "non-primary"
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


def create_pending_email_address(user: User, email: str) -> EmailAddress:
    email = email.strip().lower()

    email_address = EmailAddress.objects.create(
        user=user, email=email, primary=False, verified=False
    )
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
