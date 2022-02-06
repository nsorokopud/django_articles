from typing import Iterable, List, Optional
import logging

from django.contrib.auth.models import User
from django.template.defaultfilters import slugify

from .models import Article, ArticleCategory


logger = logging.getLogger("default_logger")


def find_published_articles() -> Iterable[Article]:
    return Article.objects.filter(is_published=True)


def get_all_categories() -> Iterable[ArticleCategory]:
    return ArticleCategory.objects.all()


def get_all_users_that_liked_article(article_slug: str) -> Iterable[User]:
    try:
        article = Article.objects.get(slug=article_slug)
        return article.users_that_liked.all()
    except Article.DoesNotExist:
        logger.error(
            f"Tried to get users that liked a non-existent article with slug={article_slug}"
        )
        return list()


def create_article(
    title: str,
    category: ArticleCategory,
    author: User,
    preview_text: str,
    content: str,
    tags: Optional[List] = None,
    preview_image: Optional[str] = None,
) -> Article:
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


def toggle_article_like(article_slug: str, user_id: int) -> Optional[int]:
    try:
        article = Article.objects.get(slug=article_slug)
        try:
            user = article.users_that_liked.get(id=user_id)
            article.users_that_liked.remove(user)
        except User.DoesNotExist:
            user = User.objects.get(id=user_id)
            article.users_that_liked.add(user)
        return article.get_likes_count()
    except Article.DoesNotExist:
        logger.error(f"Tried to get a non-existent article with slug={article_slug}")
        return None
