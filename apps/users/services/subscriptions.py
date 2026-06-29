import logging

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from ..cache import get_subscribers_count_cache_key
from ..models import AuthorSubscription, User


logger = logging.getLogger(__name__)


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


def get_new_articles_summary(
    *, user_id: int, since_publish_sequence: int = 0
) -> dict[str, bool | int]:
    last_seen = (
        User.objects.filter(pk=user_id)
        .values_list("subscriptions_last_seen_publish_sequence", flat=True)
        .get()
    )

    watermark = max(since_publish_sequence or 0, last_seen)

    latest = AuthorSubscription.objects.filter(
        subscriber_id=user_id,
        notifications_enabled=True,
        author__latest_article_publish_sequence__gt=watermark,
    ).aggregate(latest=Max("author__latest_article_publish_sequence"))["latest"]

    if latest is None:
        return {"has_new": False, "latest_article_publish_sequence": watermark}
    return {"has_new": True, "latest_article_publish_sequence": latest}


def advance_subscriptions_last_seen_publish_sequence(
    *, user_id: int, last_seen_publish_sequence: int
) -> None:
    if last_seen_publish_sequence <= 0:
        return
    User.objects.filter(
        id=user_id,
        subscriptions_last_seen_publish_sequence__lt=last_seen_publish_sequence,
    ).update(subscriptions_last_seen_publish_sequence=last_seen_publish_sequence)


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
