from typing import List, Optional

from sql_util.utils import SubqueryAggregate
from taggit.models import TaggedItem

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify

from articles.models import Article, ArticleCategory, ArticleComment


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


def find_articles_with_tag(tag: str) -> QuerySet[Article]:
    articles_with_tag__ids = TaggedItem.objects.filter(tag__name=tag).values_list(
        "object_id", flat=True
    )
    return find_published_articles().filter(id__in=articles_with_tag__ids)


def find_articles_by_query(q: str) -> QuerySet[Article]:
    articles_with_tags_containing_q__ids = TaggedItem.objects.filter(
        tag__name__icontains=q
    ).values_list("object_id", flat=True)
    return (
        find_published_articles()
        .filter(
            Q(title__icontains=q)
            | Q(content__icontains=q)
            | Q(category__title__icontains=q)
            | Q(id__in=articles_with_tags_containing_q__ids)
        )
        .distinct()
    )


def find_article_comments_liked_by_user(article_slug: str, user: User) -> List[int]:
    comments = ArticleComment.objects.filter(article__slug=article_slug).prefetch_related(
        "users_that_liked"
    )
    return [comment.id for comment in comments if user in comment.users_that_liked.all()]


def find_comments_to_article(article_slug: str) -> QuerySet[ArticleComment]:
    return (
        ArticleComment.objects.filter(article__slug=article_slug)
        .select_related("author")
        .select_related("author__profile")
        .annotate(likes_count=Count("users_that_liked", distinct=True))
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


def increment_article_views_counter(article_slug: str) -> Article:
    article = get_object_or_404(Article, slug=article_slug)
    article.views_count = F("views_count") + 1
    article.save(update_fields=("views_count",))
    article.refresh_from_db()
    return article


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
        ArticleComment.objects.annotate(likes_count=Count("users_that_liked", distinct=True))
        .get(id=comment_id)
        .likes_count
    )
    return likes_count


def _generate_unique_article_slug(article_title: str):
    slug = slugify(article_title)
    unique_slug = slug

    number = 1
    while Article.objects.filter(slug=unique_slug).exists():
        unique_slug = f'{slug}-{number}'
        number += 1
    
    return unique_slug
