import logging

from django.core.paginator import Page, Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F

from notifications.services.creation import create_new_comment_notification
from notifications.services.dispatch import dispatch_notification_after_commit
from users.models import User

from ..models import Article, ArticleComment, ArticleStatus
from ..selectors import find_article_comments_liked_by_user, find_comments_to_article
from ..settings import ARTICLE_COMMENTS_PER_PAGE


logger = logging.getLogger(__name__)


def create_article_comment(*, article_id: int, user: User, text: str) -> ArticleComment:
    """Creates an article comment and schedules related notification dispatch."""
    with transaction.atomic():
        article = Article.objects.select_for_update().get(pk=article_id)

        if article.status != ArticleStatus.PUBLISHED:
            raise ValueError("comments can only be added to published articles")

        comment = ArticleComment.objects.create(article=article, author=user, text=text)

        Article.objects.filter(pk=article.pk).update(
            comments_count=F("comments_count") + 1
        )

        notification_data = {
            "comment_id": comment.id,
            "comment_author_id": user.id,
            "comment_author_username": user.username,
            "article_id": article.id,
            "article_author_id": article.author_id,
            "article_slug": article.slug,
            "article_title": article.title,
        }

    try:
        with transaction.atomic():
            notification_result = create_new_comment_notification(**notification_data)

            if notification_result is not None:
                notification, created = notification_result
                dispatch_notification_after_commit(
                    notification_id=notification.id,
                    notification_type=notification.notification_type,
                    is_new_unread=created,
                )
    except (IntegrityError, RuntimeError):
        logger.exception(
            "Failed to create notification for article comment %s "
            "(article_id=%s, user_id=%s)",
            comment.id,
            notification_data["article_id"],
            user.id,
        )

    return comment


def decrement_article_comments_count(*, article_id: int) -> None:
    Article.objects.filter(pk=article_id, comments_count__gt=0).update(
        comments_count=F("comments_count") - 1
    )


def get_article_comments_page(
    *,
    article: Article,
    page_number: int | str | None = 1,
    user: User | None = None,
) -> tuple[Page, set[int]]:
    comments_qs = find_comments_to_article(article)
    paginator = Paginator(comments_qs, ARTICLE_COMMENTS_PER_PAGE)
    comments_page = paginator.get_page(page_number)

    liked_comments: set[int] = set()
    if user and user.is_authenticated:
        comment_ids = [comment.id for comment in comments_page.object_list]
        if comment_ids:
            liked_comments = set(find_article_comments_liked_by_user(comment_ids, user))

    return comments_page, liked_comments


def sync_article_comments_count(*, batch_size: int = 1000) -> None:
    last_id = 0

    while True:
        articles = list(
            Article.objects.filter(id__gt=last_id)
            .order_by("id")
            .annotate(real_comments_count=Count("articlecomment", distinct=True))
            .only("id", "comments_count")[:batch_size]
        )

        if not articles:
            break

        for article in articles:
            if article.comments_count != article.real_comments_count:
                Article.objects.filter(pk=article.pk).update(
                    comments_count=article.real_comments_count
                )

        last_id = articles[-1].id
