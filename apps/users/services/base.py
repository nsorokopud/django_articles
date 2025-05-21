import logging
from typing import Optional

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Count
from django.db.models.query import QuerySet

from users.models import Profile, User


logger = logging.getLogger("default_logger")


def create_user_profile(user: User) -> Profile:
    profile = Profile.objects.create(user=user)
    return profile


def deactivate_user(user: User) -> None:
    user.is_active = False
    user.save()


def activate_user(user):
    user.is_active = True
    user.save()
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )


def get_all_users() -> QuerySet[User]:
    return User.objects.all()


def get_user_by_id(user_id: int) -> User:
    return User.objects.get(id=user_id)


def get_user_by_username(username: str) -> User:
    return User.objects.get(username=username)


def find_user_profiles_with_subscribers() -> QuerySet[Profile]:
    """Returns a queryset of profiles belonging to users that have at
    least 1 subscriber.
    """
    return Profile.objects.annotate(subscribers_count=Count("subscribers")).filter(
        subscribers_count__gt=0
    )


def get_all_supscriptions_of_user(user: User) -> list[str]:
    """Returns a list of usernames of all authors the specified user is
    subscribed to.
    """
    return [p.user.username for p in user.subscribed_profiles.all()]


def toggle_user_supscription(user: User, author: User) -> None:
    """Adds user to the list of author's subscribers if that user is not
    in the list. Otherwise removes the user from the list.
    """
    if user.pk != author.pk:
        if user not in author.profile.subscribers.all():
            author.profile.subscribers.add(user)
        else:
            author.profile.subscribers.remove(user)


def enforce_unique_email_type_per_user(instance: EmailAddress) -> None:
    """Ensures that a user has at most one email address of each type (primary or
    non-primary). Raises `ValidationError` if the user already has an email address with
    the same `primary` value.
    """
    queryset = EmailAddress.objects.filter(user=instance.user, primary=instance.primary)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    if queryset.exists():
        address_type = "primary" if instance.primary else "non-primary"
        raise ValidationError(f"This user already has a {address_type} email address.")


def create_pending_email_address(user: User, email: str) -> EmailAddress:
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


def get_pending_email_address(user: User) -> Optional[EmailAddress]:
    try:
        return EmailAddress.objects.get(user=user, primary=False, verified=False)
    except EmailAddress.DoesNotExist:
        return None


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
    for account in accounts:
        account.delete()
        logger.info("SocialAccount(id=%s) was removed.", account.id)


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
    user.email = new_email.email
    user.save(update_fields=["email"])

    # Bypass pre-save signal that enforces email validation
    EmailAddress.objects.filter(id=old_email.id).update(primary=False)
    EmailAddress.objects.filter(id=new_email.id).update(primary=True, verified=True)

    old_email.delete()
    logger.info("EmailAddress(id=%s) was deleted.", old_email.id)
    delete_social_accounts_with_email(old_email.email)
    logger.info(
        "User(id=%s) changed email from (id=%s) to (id=%s)",
        user_id,
        old_email.id,
        new_email.id,
    )
