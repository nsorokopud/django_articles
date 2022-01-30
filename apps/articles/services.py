from typing import Iterable

from .models import Article, ArticleCategory


def find_published_articles() -> Iterable[Article]:
    return Article.objects.filter(is_published=True)


def get_all_categories() -> Iterable[ArticleCategory]:
    return ArticleCategory.objects.all()
