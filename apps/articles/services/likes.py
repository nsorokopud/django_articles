from django.db import transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404

from ..models import Article, ArticleComment, ArticleStatus


@transaction.atomic
def set_article_like(
    *, article_slug: str, user_id: int, liked: bool
) -> tuple[int, bool]:
    article = get_object_or_404(
        Article.objects.select_for_update(),
        slug=article_slug,
        status=ArticleStatus.PUBLISHED,
    )
    return _set_like(article, user_id=user_id, liked=liked)


@transaction.atomic
def set_comment_like(*, comment_id: int, user_id: int, liked: bool) -> tuple[int, bool]:
    comment = get_object_or_404(
        ArticleComment.objects.only("id", "article_id"), id=comment_id
    )

    get_object_or_404(
        Article.objects.select_for_update(),
        pk=comment.article_id,
        status=ArticleStatus.PUBLISHED,
    )

    return _set_like(comment, user_id=user_id, liked=liked)


def _set_like(
    obj: Article | ArticleComment, *, user_id: int, liked: bool
) -> tuple[int, bool]:
    through = obj.users_that_liked.through
    source_field_name = obj.users_that_liked.source_field_name
    target_field_name = obj.users_that_liked.target_field_name

    source_id_field = f"{source_field_name}_id"
    target_id_field = f"{target_field_name}_id"

    lookup = {source_id_field: obj.pk, target_id_field: user_id}

    model = type(obj)

    if liked:
        final_liked = _like(through=through, model=model, obj_id=obj.pk, lookup=lookup)
    else:
        final_liked = _unlike(
            through=through, model=model, obj_id=obj.pk, lookup=lookup
        )

    likes_count = model.objects.values_list("likes_count", flat=True).get(pk=obj.pk)

    return likes_count, final_liked


def sync_article_likes_count(*, batch_size: int = 1000) -> None:
    _sync_likes_count(model=Article, batch_size=batch_size)


def sync_comment_likes_count(*, batch_size: int = 1000) -> None:
    _sync_likes_count(model=ArticleComment, batch_size=batch_size)


def _like(*, through, model, obj_id: int, lookup: dict) -> bool:
    created = through.objects.get_or_create(**lookup)[1]

    if created:
        model.objects.filter(pk=obj_id).update(likes_count=F("likes_count") + 1)

    return True


def _unlike(*, through, model, obj_id: int, lookup: dict) -> bool:
    deleted_count, _ = through.objects.filter(**lookup).delete()

    if deleted_count:
        model.objects.filter(pk=obj_id, likes_count__gt=0).update(
            likes_count=F("likes_count") - 1
        )

    return False


def _sync_likes_count(*, model, batch_size: int) -> None:
    last_id = 0

    while True:
        objects = list(
            model.objects.filter(id__gt=last_id)
            .order_by("id")
            .annotate(real_likes_count=Count("users_that_liked", distinct=True))
            .only("id", "likes_count")[:batch_size]
        )

        if not objects:
            break

        for obj in objects:
            if obj.likes_count != obj.real_likes_count:
                model.objects.filter(pk=obj.pk).update(likes_count=obj.real_likes_count)

        last_id = objects[-1].id
