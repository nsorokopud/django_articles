import logging
from typing import Optional

from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import Article, ArticleComment


logger = logging.getLogger("default_logger")


def toggle_article_like(article_slug: str, user_id: int) -> int:
    article = get_object_or_404(Article, slug=article_slug)
    return toggle_like(article, user_id)


def toggle_comment_like(comment_id: int, user_id: int) -> Optional[int]:
    comment = get_object_or_404(ArticleComment, id=comment_id)
    return toggle_like(comment, user_id)


@transaction.atomic
def toggle_like(obj: Article | ArticleComment, user_id: int) -> int:
    if obj.users_that_liked.filter(id=user_id).exists():
        obj.users_that_liked.remove(user_id)
    else:
        obj.users_that_liked.add(user_id)

    return obj.users_that_liked.count()
