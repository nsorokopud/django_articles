from typing import Iterable, List, Optional
import logging

from django.db.models import Q
from django.db.models.query import QuerySet
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify

from .models import Article, ArticleCategory, ArticleComment


logger = logging.getLogger("default_logger")


def find_published_articles() -> QuerySet[Article]:
    return Article.objects.filter(is_published=True)


def find_articles_of_category(category_slug: str) -> QuerySet[Article]:
    return find_published_articles().filter(category__slug=category_slug)


def find_articles_by_query(q: str) -> QuerySet[Article]:
    return (
        find_published_articles()
        .filter(
            Q(title__icontains=q)
            | Q(category__title__icontains=q)
            | Q(tags__name__icontains=q)
            | Q(content__icontains=q)
        )
        .distinct()
    )


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


def toggle_comment_like(comment_id: int, user_id: int) -> Optional[int]:
    try:
        comment = ArticleComment.objects.get(id=comment_id)
        try:
            user = comment.users_that_liked.get(id=user_id)
            comment.users_that_liked.remove(user)
        except User.DoesNotExist:
            user = User.objects.get(id=user_id)
            comment.users_that_liked.add(user)
        return comment.get_likes_count()
    except ArticleComment.DoesNotExist:
        logger.error(f"Tried to get a non-existent comment with id={comment_id}")
        return None
