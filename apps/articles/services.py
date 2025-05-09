import os
from typing import IO, Iterable, List, Optional
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify
from sql_util.utils import SubqueryAggregate
from taggit.models import Tag

from articles.models import Article, ArticleCategory, ArticleComment
from users.models import User


def find_published_articles() -> QuerySet[Article]:
    return (
        Article.objects.filter(is_published=True)
        .select_related("category")
        .select_related("author")
        .select_related("author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .annotate(comments_count=Count("articlecomment", distinct=True))
        .order_by("-created_at")
    )


def find_articles_of_category(category_slug: str) -> QuerySet[Article]:
    return find_published_articles().filter(category__slug=category_slug)


def find_articles_with_tags(
    tags: Iterable[str], queryset: Optional[QuerySet[Article]] = None
) -> QuerySet[Article]:
    if queryset is None:
        queryset = find_published_articles()

    for tag in tags:
        queryset = queryset.filter(tags__name=tag)
    return queryset


def find_articles_by_query(
    q: str, queryset: Optional[QuerySet[Article]] = None
) -> QuerySet[Article]:
    if queryset is None:
        queryset = find_published_articles()

    return queryset.filter(
        Q(title__icontains=q)
        | Q(content__icontains=q)
        | Q(category__title__icontains=q)
        | Q(tags__name__icontains=q)
    ).distinct()


def find_article_comments_liked_by_user(article_slug: str, user: User) -> QuerySet[int]:
    """Returns ids of `ArticleComment` instances liked by the user"""
    return ArticleComment.objects.filter(
        article__slug=article_slug, users_that_liked=user
    ).values_list("id", flat=True)


def find_comments_to_article(article_slug: str) -> QuerySet[ArticleComment]:
    return (
        ArticleComment.objects.filter(article__slug=article_slug)
        .select_related("author")
        .select_related("author__profile")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
    )


def get_article_by_id(article_id: int) -> Article:
    return (
        Article.objects.select_related("author")
        .select_related("author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(id=article_id)
    )


def get_article_by_slug(article_slug: str) -> Article:
    return (
        Article.objects.select_related("author")
        .select_related("author__profile")
        .prefetch_related("tags")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(slug=article_slug)
    )


def get_all_categories() -> QuerySet[ArticleCategory]:
    return ArticleCategory.objects.annotate(
        articles_count=SubqueryAggregate(
            "article__id", filter=Q(is_published=True), aggregate=Count
        )
    )


def get_all_tags():
    return Tag.objects.all()


def get_all_users_that_liked_article(article_slug: str) -> QuerySet[User]:
    article = get_object_or_404(Article, slug=article_slug)
    return article.users_that_liked.all()


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


def get_comment_by_id(comment_id: int) -> ArticleComment:
    return ArticleComment.objects.get(id=comment_id)


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
