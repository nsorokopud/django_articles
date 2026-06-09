from django.core.management.base import BaseCommand

from articles.models import Article
from articles.search_utils import extract_searchable_text


class Command(BaseCommand):
    help = "Backfill content_text for articles"

    def handle(self, *args, **options):
        batch = []
        batch_size = 500

        for article in Article.objects.all().iterator():
            article.content_text = extract_searchable_text(article.content)
            batch.append(article)

            if len(batch) >= batch_size:
                Article.objects.bulk_update(
                    batch, ["content_text"], batch_size=batch_size
                )
                batch.clear()

        if batch:
            Article.objects.bulk_update(batch, ["content_text"], batch_size=batch_size)

        self.stdout.write(
            self.style.SUCCESS("Article content_text backfilled successfully")
        )
