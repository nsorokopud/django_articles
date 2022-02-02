from typing import Iterable, List, Optional

from django.contrib.auth.models import User
from django.template.defaultfilters import slugify

from .models import Article, ArticleCategory


def find_published_articles() -> Iterable[Article]:
    return Article.objects.filter(is_published=True)


def get_all_categories() -> Iterable[ArticleCategory]:
    return ArticleCategory.objects.all()


def create_article(
    title: str,
    category: ArticleCategory,
    author: User,
    preview_text: str,
    content: str,
    tags: Optional[List] = None,
    preview_image: Optional[str] = None,
):
    article = Article.objects.create(
        title=title,
        category=category,
        author=author,
        preview_text=preview_text,
        preview_image=preview_image,
        content=content,
        is_published=True,
    )
    article.slug = slugify(title)
    if not tags:
        tags = []
    article.tags.add(*tags)
    article.save()
    return article
