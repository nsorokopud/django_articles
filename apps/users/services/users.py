import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from users.models import Profile, User


logger = logging.getLogger("default_logger")


def activate_user(user):
    user.is_active = True
    user.save()
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )


def deactivate_user(user: User) -> None:
    user.is_active = False
    user.save()


def create_user_profile(user: User) -> Profile:
    profile = Profile.objects.create(user=user)
    return profile


@transaction.atomic
def toggle_user_subscription(user: User, author: User) -> None:
    """Adds user to the list of author's subscribers if that user is not
    in the list. Otherwise removes the user from the list.
    """
    if not user.is_authenticated:
        raise ValidationError("Anonymous users cannot subscribe to authors")
    if not user.is_active:
        raise ValidationError("Inactive users cannot subscribe to authors")
    if user.pk == author.pk:
        raise ValidationError("Users cannot subscribe to themselves")
    if not author.is_active:
        raise ValidationError("Cannot subscribe to non-active authors")

    try:
        author_profile = Profile.objects.select_for_update().get(user=author)
    except Profile.DoesNotExist as e:
        raise ValidationError("Author does not have a profile") from e

    subscribers = author_profile.subscribers
    if not subscribers.filter(pk=user.pk).exists():
        subscribers.add(user)
        logger.info("User %s subscribed to author %s", user.id, author.id)
    else:
        subscribers.remove(user)
        logger.info("User %s unsubscribed from author %s", user.id, author.id)


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
