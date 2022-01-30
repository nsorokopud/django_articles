from typing import Iterable

from .models import Article


def find_published_articles() -> Iterable[Article]:
    return Article.objects.filter(is_published=True)
