import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from users.models import AuthorSubscription, Profile, User

from ..cache import get_subscribers_count_cache_key


logger = logging.getLogger(__name__)


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
        user.refresh_from_db()
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
def set_author_subscription(
    *, subscriber: User, author: User, should_subscribe: bool
) -> tuple[bool, bool]:
    """Sets the desired subscription state.

    Returns:
        (is_subscribed, changed)

        is_subscribed:
            Final state after the operation.

        changed:
            True if the DB row was created or deleted.
            False if the requested state already existed.
    """
    _validate_subscription_action(subscriber=subscriber, author=author)

    if should_subscribe:
        changed = _subscribe_to_author(subscriber=subscriber, author=author)
        return True, changed

    changed = _unsubscribe_from_author(subscriber=subscriber, author=author)
    return False, changed


def advance_latest_article_publish_sequence(
    *, user_id: int, publish_sequence: int
) -> None:
    User.objects.filter(
        id=user_id,
        latest_article_publish_sequence__lt=publish_sequence,
    ).update(latest_article_publish_sequence=publish_sequence)


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


def _validate_subscription_action(*, subscriber: User, author: User) -> None:
    if not subscriber.is_authenticated:
        raise ValidationError("Anonymous users cannot subscribe to authors.")

    if not subscriber.is_active:
        raise ValidationError("Inactive users cannot subscribe to authors.")

    if subscriber.pk == author.pk:
        raise ValidationError("Users cannot subscribe to themselves.")

    if not author.is_active:
        raise ValidationError("Cannot subscribe to inactive authors.")


def _subscribe_to_author(*, subscriber: User, author: User) -> bool:
    _, created = AuthorSubscription.objects.get_or_create(
        subscriber=subscriber, author=author
    )

    if created:
        logger.info("User %s subscribed to author %s", subscriber.id, author.id)
        _invalidate_subscribers_count_cache_after_commit(author_id=author.id)
    else:
        logger.info(
            "User %s was already subscribed to author %s", subscriber.id, author.id
        )

    return created


def _unsubscribe_from_author(*, subscriber: User, author: User) -> bool:
    deleted_count, _ = AuthorSubscription.objects.filter(
        subscriber=subscriber, author=author
    ).delete()

    changed = deleted_count > 0

    if changed:
        logger.info("User %s unsubscribed from author %s", subscriber.id, author.id)
        _invalidate_subscribers_count_cache_after_commit(author_id=author.id)
    else:
        logger.info("User %s was not subscribed to author %s", subscriber.id, author.id)

    return changed


def _invalidate_subscribers_count_cache_after_commit(*, author_id: int) -> None:
    transaction.on_commit(
        lambda: cache.delete(get_subscribers_count_cache_key(author_id))
    )
