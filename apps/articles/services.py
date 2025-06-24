import os
from typing import IO, List, Optional
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify

from users.models import User

from .models import Article, ArticleCategory, ArticleComment
from .selectors import get_article_by_id


@transaction.atomic
def create_article(
    *,
    title: str,
    author: User,
    preview_text: str,
    content: str,
    category: Optional[ArticleCategory] = None,
    tags: Optional[List] = None,
    preview_image: Optional[str] = None,
) -> Article:
    article = Article(
        title=title,
        category=category,
        author=author,
        preview_text=preview_text,
        preview_image=preview_image,
        content=content,
        is_published=True,
    )
    article.slug = _generate_unique_article_slug(title)
    article.save()
    if tags is not None:
        article.tags.add(*tags)
    return article


def increment_article_views_counter(article: Article) -> int:
    article.views_count = F("views_count") + 1
    article.save(update_fields=("views_count",))
    article.refresh_from_db()
    return article.views_count


def toggle_article_like(article_slug: str, user_id: int) -> int:
    article = get_object_or_404(Article, slug=article_slug)
    try:
        user = article.users_that_liked.get(id=user_id)
        article.users_that_liked.remove(user)
    except User.DoesNotExist:
        user = get_object_or_404(User, id=user_id)
        article.users_that_liked.add(user)
    likes_count = (
        Article.objects.annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(slug=article_slug)
        .likes_count
    )
    return likes_count


def toggle_comment_like(comment_id: int, user_id: int) -> Optional[int]:
    comment = get_object_or_404(ArticleComment, id=comment_id)
    try:
        user = comment.users_that_liked.get(id=user_id)
        comment.users_that_liked.remove(user)
    except User.DoesNotExist:
        user = User.objects.get(id=user_id)
        comment.users_that_liked.add(user)
    likes_count = (
        ArticleComment.objects.annotate(
            likes_count=Count("users_that_liked", distinct=True)
        )
        .get(id=comment_id)
        .likes_count
    )
    return likes_count


def _generate_unique_article_slug(article_title: str):
    """Returns a unique slug for the specified article title. If an
    article with the specified title already exists, the corresponding
    slug is returned. Otherwise the next available unique slug is
    returned.
    """
    try:
        article = Article.objects.get(title=article_title)
        return article.slug
    except Article.DoesNotExist:
        slug = slugify(article_title)
        unique_slug = slug

        number = 1
        while Article.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{slug}-{number}"
            number += 1

        return unique_slug


def save_media_file_attached_to_article(file: IO, article_id: int) -> tuple[str, str]:
    article = get_article_by_id(article_id)
    name, extension = str(file).split(".")
    filename = f"{name}_{uuid4()}.{extension}"
    directory = os.path.join(
        "articles", "uploads", article.author.username, str(article_id)
    )
    file_path = os.path.join(directory, filename)
    default_storage.save(file_path, file)
    return file_path, article.get_absolute_url()


def delete_media_files_attached_to_article(article: Article) -> None:
    article_dir = os.path.join(
        "articles", "uploads", article.author.username, str(article.id)
    )
    if default_storage.exists(article_dir):
        for file in default_storage.listdir(article_dir)[1]:
            default_storage.delete(os.path.join(article_dir, file))
        default_storage.delete(article_dir)
