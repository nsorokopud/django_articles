from django.db import transaction

from users.models import User


def advance_latest_article_publish_sequence(
    *, user_id: int, publish_sequence: int
) -> None:
    User.objects.filter(
        id=user_id,
        latest_article_publish_sequence__lt=publish_sequence,
    ).update(latest_article_publish_sequence=publish_sequence)


@transaction.atomic
def recompute_latest_article_publish_sequence(*, user_id: int) -> int:
    from articles.models import Article, ArticleStatus

    User.objects.select_for_update().only("id").get(pk=user_id)

    latest = (
        Article.objects.filter(
            author_id=user_id,
            status=ArticleStatus.PUBLISHED,
            publish_sequence__isnull=False,
        )
        .order_by("-publish_sequence")
        .values_list("publish_sequence", flat=True)
        .first()
    ) or 0

    User.objects.filter(pk=user_id).update(latest_article_publish_sequence=latest)
    return latest
