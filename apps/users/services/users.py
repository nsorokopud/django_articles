import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from users.models import Profile, User

from ..cache import get_subscribers_count_cache_key


logger = logging.getLogger("default_logger")


@transaction.atomic
def activate_user(user: User) -> None:
    user_updated = User.objects.filter(pk=user.pk).update(is_active=True)
    if user_updated:
        logger.info("User %s was activated", user.id)
    else:
        logger.warning("No user found with id %s to activate", user.id)
    _, email_created = EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    if email_created:
        logger.info("EmailAddress(user_id=%s) was created", user.id)
    else:
        logger.info("EmailAddress(user_id=%s) was updated", user.id)


def deactivate_user(user: User) -> None:
    updated = User.objects.filter(pk=user.pk).update(is_active=False)
    if updated:
        logger.info("User %s was deactivated", user.id)
    else:
        logger.warning(
            "Tried to deactivate user %s but no matching user found", user.id
        )


@transaction.atomic
def create_user_profile(user: User) -> Profile:
    profile, created = Profile.objects.get_or_create(user=user)
    if created:
        logger.info("Profile for user %s was created", user.id)
    else:
        logger.info("Profile for user %s already exists", user.id)
    return profile


@transaction.atomic
def toggle_user_subscription(user: User, author: User) -> bool:
    """Adds user to the list of author's subscribers if that user is not
    in the list. Otherwise removes the user from the list.

    Returns:
        True if the user was subscribed, False if unsubscribed.
    """
    if not user.is_authenticated:
        raise ValidationError("Anonymous users cannot subscribe to authors.")
    if not user.is_active:
        raise ValidationError("Inactive users cannot subscribe to authors.")
    if user.pk == author.pk:
        raise ValidationError("Users cannot subscribe to themselves.")
    if not author.is_active:
        raise ValidationError("Cannot subscribe to inactive authors.")

    try:
        author_profile = Profile.objects.select_for_update().get(user=author)
    except Profile.DoesNotExist as e:
        raise ValidationError("Author does not have a profile.") from e

    subscribers = author_profile.subscribers
    if subscribers.filter(pk=user.pk).exists():
        subscribers.remove(user)
        logger.info("User %s unsubscribed from author %s", user.id, author.id)
        return False
    subscribers.add(user)
    logger.info("User %s subscribed to author %s", user.id, author.id)

    cache.delete(get_subscribers_count_cache_key(author.id))

    return True


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
