import logging

from django.db import DatabaseError, transaction
from django.db.models import Case, F, IntegerField, Value, When

from ..models import Article


logger = logging.getLogger(__name__)


def bulk_increment_article_view_counts(view_deltas: dict[int, int]) -> None:
    """Increment article view counts in the DB using a single bulk
    UPDATE with CASE.

    view_deltas: a dictionary mapping article IDs to numbers of views
    to increment with.
    """
    if not view_deltas:
        logger.warning("No deltas to process for bulk update.")
        return

    when_clauses = [
        When(pk=article_id, then=F("views_count") + Value(view_delta))
        for article_id, view_delta in sorted(view_deltas.items())
    ]

    try:
        with transaction.atomic():
            Article.objects.filter(pk__in=view_deltas).update(
                views_count=Case(
                    *when_clauses, default=F("views_count"), output_field=IntegerField()
                )
            )
    except DatabaseError:
        logger.exception("Failed to bulk update view counts.")
        raise
