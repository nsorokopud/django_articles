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
    user = User.objects.select_for_update().get(pk=user.pk)
    email = (user.email or "").strip().lower()

    if not email:
        raise ValidationError("User email is required for activation.")

    update_fields = []

    if user.email != email:
        user.email = email
        update_fields.append("email")

    if not user.is_active:
        user.is_active = True
        update_fields.append("is_active")

    if update_fields:
        user.save(update_fields=update_fields)
        logger.info("User %s activation state was updated.", user.id)
    else:
        logger.info("User %s was already active with normalized email.", user.id)

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

    # Bypass EmailAddress pre-save validation while repairing primary state
    primary_addresses.update(primary=False)

    if matching_email_address is None:
        email_address = EmailAddress.objects.create(
            user_id=user.id, email=email, verified=True, primary=True
        )

        logger.info(
            "EmailAddress(id=%s, user_id=%s) was created.", email_address.id, user.id
        )
        return

    EmailAddress.objects.filter(pk=matching_email_address.pk).update(
        email=email, verified=True, primary=True
    )

    logger.info(
        "EmailAddress(id=%s, user_id=%s) was updated.",
        matching_email_address.id,
        user.id,
    )


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
