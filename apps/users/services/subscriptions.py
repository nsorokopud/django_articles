from django.db.models import Max

from ..models import AuthorSubscription, User


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
