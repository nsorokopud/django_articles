from django.db import connection, transaction
from django.utils import timezone

from users.services.users import advance_latest_article_publish_sequence

from ..models import Article, ArticleStatus


@transaction.atomic
def publish_article(*, article_id: int) -> Article:
    a = Article.objects.select_for_update().get(id=article_id)

    if a.status == ArticleStatus.PUBLISHED:
        return a

    seq = get_next_article_publish_sequence_value()
    a.status = ArticleStatus.PUBLISHED
    a.published_at = timezone.now()
    a.publish_sequence = seq
    a.save(update_fields=["status", "published_at", "publish_sequence"])

    advance_latest_article_publish_sequence(user_id=a.author_id, publish_sequence=seq)
    return a


def get_next_article_publish_sequence_value() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('article_publish_seq')")
        return int(cursor.fetchone()[0])
