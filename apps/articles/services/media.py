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

from ..media_paths import extract_article_media_storage_name_for_article
from ..models import Article, ArticleMedia


logger = logging.getLogger(__name__)

ARTICLE_MEDIA_UNUSED_GRACE_PERIOD = timedelta(days=7)

_UPLOAD_ERRORS = (
    OSError,
    BotoCoreError,
    ClientError,
    S3UploadFailedError,
    SuspiciousFileOperation,
)

_STORAGE_DELETE_ERRORS = (OSError, BotoCoreError, ClientError, SuspiciousFileOperation)


def save_article_inline_media_file(file: BinaryIO, article: Article) -> str:
    media = ArticleMedia(article=article, unreferenced_at=timezone.now())

    try:
        media.file.save(file.name, file, save=False)
    except _UPLOAD_ERRORS as e:
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
    media = ArticleMedia.objects.filter(article_id=article.id)

    media.filter(file__in=referenced_files).update(unreferenced_at=None)

    media.filter(unreferenced_at__isnull=True).exclude(
        file__in=referenced_files
    ).update(unreferenced_at=timezone.now())


def cleanup_unused_article_inline_media(*, batch_size: int = 500) -> int:
    now = timezone.now()

    # Recover orphaned media that bypassed the article deletion service
    ArticleMedia.objects.filter(
        article_id__isnull=True, unreferenced_at__isnull=True
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
        if not isinstance(src, str):
            continue

        file_name = extract_article_media_storage_name_for_article(
            src, article_id=article_id, author_id=author_id
        )
        if file_name:
            file_names.add(file_name)

    return file_names


@transaction.atomic
def _delete_unused_article_inline_media(*, media_id: int, cutoff: datetime) -> int:
    media_query = ArticleMedia.objects.filter(id=media_id, unreferenced_at__lt=cutoff)

    article_id = media_query.values_list("article_id", flat=True).first()

    if article_id is not None:
        article_exists = (
            Article.objects.select_for_update().filter(id=article_id).exists()
        )
        if not article_exists:
            return 0

        media_query = media_query.filter(article_id=article_id)
    else:
        media_query = media_query.filter(article_id__isnull=True)

    media = media_query.select_for_update().first()
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
    except _STORAGE_DELETE_ERRORS:
        logger.exception("Failed to roll back uploaded media file: %s", file_name)
