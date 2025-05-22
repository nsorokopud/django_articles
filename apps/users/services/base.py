import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.db import connection, transaction

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


def toggle_user_supscription(user: User, author: User) -> None:
    """Adds user to the list of author's subscribers if that user is not
    in the list. Otherwise removes the user from the list.
    """
    if user.pk != author.pk:
        if user not in author.profile.subscribers.all():
            author.profile.subscribers.add(user)
        else:
            author.profile.subscribers.remove(user)


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
