from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Reset article_publish_seq to match the max publish_sequence in articles"

    def handle(self, *args, **options) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT setval(
                    'article_publish_seq',
                    COALESCE(
                        (SELECT MAX(publish_sequence) FROM articles_article),
                        1
                    ),
                    (SELECT MAX(publish_sequence) IS NOT NULL FROM articles_article)
                )
                """
            )

        self.stdout.write(
            self.style.SUCCESS("article_publish_seq successfully synchronized")
        )
