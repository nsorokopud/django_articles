import logging
from datetime import datetime, timedelta
from typing import BinaryIO

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from bs4 import BeautifulSoup
from django.core.exceptions import SuspiciousFileOperation
from django.db import DatabaseError, transaction
from django.utils import timezone

from core.exceptions import MediaSaveError

from ..media_paths import (
    extract_article_media_storage_name,
    is_article_media_storage_name_for_article,
)
from ..models import Article, ArticleMedia


logger = logging.getLogger(__name__)

ARTICLE_MEDIA_UNUSED_GRACE_PERIOD = timedelta(days=7)


def save_article_inline_media_file(file: BinaryIO, article: Article) -> str:
    media = ArticleMedia(article=article, unreferenced_at=timezone.now())

    try:
        media.file.save(file.name, file, save=False)
    except (
        OSError,
        BotoCoreError,
        ClientError,
        S3UploadFailedError,
        SuspiciousFileOperation,
    ) as e:
        _delete_failed_inline_upload(media)
        logger.exception("Failed to upload media for article %s", article.id)
        raise MediaSaveError("Could not save the uploaded file.") from e

    try:
        media.save()
    except DatabaseError as e:
        _delete_failed_inline_upload(media)
        logger.exception("Failed to create media record for article %s", article.id)
        raise MediaSaveError("Could not save the uploaded file.") from e

    return media.file.name


def sync_article_inline_media_references(*, article: Article) -> None:
    referenced_files = extract_article_inline_media_file_names(
        article.content, article_id=article.id, author_id=article.author_id
    )

    now = timezone.now()

    if referenced_files:
        ArticleMedia.objects.filter(
            article_id=article.id, file__in=referenced_files
        ).update(unreferenced_at=None)

    ArticleMedia.objects.filter(
        article_id=article.id, unreferenced_at__isnull=True
    ).exclude(file__in=referenced_files).update(unreferenced_at=now)


def cleanup_unused_article_inline_media(*, batch_size: int = 500) -> int:
    now = timezone.now()

    # Recover orphaned media that bypassed article deletion service
    ArticleMedia.objects.filter(
        article__isnull=True, unreferenced_at__isnull=True
    ).update(unreferenced_at=now)

    cutoff = now - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD

    media_ids = list(
        ArticleMedia.objects.filter(unreferenced_at__lt=cutoff)
        .order_by("unreferenced_at", "id")
        .values_list("id", flat=True)[:batch_size]
    )

    return sum(
        _delete_unused_article_inline_media(media_id=media_id, cutoff=cutoff)
        for media_id in media_ids
    )


def extract_article_inline_media_file_names(
    html: str, *, article_id: int, author_id: int
) -> set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    file_names = set()

    for img in soup.find_all("img"):
        src = img.get("src")

        file_name = extract_article_media_storage_name(
            src if isinstance(src, str) else None
        )

        if file_name and is_article_media_storage_name_for_article(
            file_name, article_id=article_id, author_id=author_id
        ):
            file_names.add(file_name)

    return file_names


@transaction.atomic
def _delete_unused_article_inline_media(*, media_id: int, cutoff: datetime) -> int:
    article_id = (
        ArticleMedia.objects.filter(id=media_id, unreferenced_at__lt=cutoff)
        .values_list("article_id", flat=True)
        .first()
    )

    if article_id is not None and not (
        Article.objects.select_for_update().filter(id=article_id).exists()
    ):
        return 0

    media_query = ArticleMedia.objects.select_for_update().filter(
        id=media_id, unreferenced_at__lt=cutoff
    )
    if article_id is None:
        media_query = media_query.filter(article__isnull=True)
    else:
        media_query = media_query.filter(article_id=article_id)

    media = media_query.first()
    if media is None:
        return 0

    file_name = media.file.name
    if file_name:
        media.file.storage.delete(file_name)

    media.delete()
    return 1


def _delete_failed_inline_upload(media: ArticleMedia) -> None:
    file_name = media.file.name
    if not file_name:
        return

    try:
        media.file.storage.delete(file_name)
    except (OSError, BotoCoreError, ClientError, SuspiciousFileOperation):
        logger.exception("Failed to roll back uploaded media file: %s", file_name)
