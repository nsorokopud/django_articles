import logging
import os
import posixpath
import shutil
from datetime import timedelta
from pathlib import PurePath, PurePosixPath
from typing import BinaryIO
from urllib.parse import unquote, urlparse

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage, default_storage
from django.utils import timezone
from storages.backends.s3boto3 import S3Boto3Storage

from core.exceptions import MediaSaveError

from ..models import Article, ArticleMedia


logger = logging.getLogger(__name__)

MAX_S3_DELETE_BATCH_SIZE = 1000
ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE = "articles/uploads/{author_id}/{article_id}"
ARTICLE_MEDIA_UNUSED_GRACE_PERIOD = timedelta(days=7)


def delete_article_media_files(
    *, article_id: int, author_id: int, preview_image_name: str = ""
) -> None:
    delete_article_inline_media_files(article_id=article_id, author_id=author_id)

    if preview_image_name:
        try:
            default_storage.delete(preview_image_name)
        except (OSError, BotoCoreError, ClientError, SuspiciousFileOperation):
            logger.exception(
                "Failed to delete preview image %s for article %s.",
                preview_image_name,
                article_id,
            )
            raise


def save_article_inline_media_file(file: BinaryIO, article: Article) -> str:
    media = ArticleMedia(article=article, unreferenced_at=timezone.now())

    try:
        media.file.save(file.name, file, save=False)
        media.save()
        return media.file.name
    except (OSError, SuspiciousFileOperation, S3UploadFailedError, ClientError) as e:
        if media.file.name:
            try:
                default_storage.delete(media.file.name)
            except (OSError, BotoCoreError, ClientError, SuspiciousFileOperation):
                logger.exception(
                    "Failed to delete media file after failed save: %s", media.file.name
                )

        logger.exception(
            "Failed to save media for article %s: %s", article.id, type(e).__name__
        )
        raise MediaSaveError("Could not save the uploaded file.") from e


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
    cutoff = timezone.now() - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD

    media_items = list(
        ArticleMedia.objects.filter(unreferenced_at__lt=cutoff)
        .order_by("id")
        .only("id", "file")[:batch_size]
    )

    deleted_count = 0

    for media in media_items:
        file_name = media.file.name

        try:
            default_storage.delete(file_name)
        except (OSError, BotoCoreError, ClientError, SuspiciousFileOperation):
            logger.exception("Failed to delete unused article media file %s", file_name)
            continue

        deleted, _ = ArticleMedia.objects.filter(
            id=media.id,
            unreferenced_at__lt=cutoff,
        ).delete()

        if deleted:
            deleted_count += 1

    return deleted_count


def delete_article_inline_media_files(article_id: int, author_id: int) -> None:
    article_dir = ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE.format(
        author_id=author_id, article_id=article_id
    )

    if isinstance(default_storage, FileSystemStorage):
        _delete_local_filesystem_media(article_dir, article_id, default_storage)
    elif isinstance(default_storage, S3Boto3Storage):
        _delete_s3_media(article_dir, article_id, default_storage)
    else:
        raise ImproperlyConfigured("Media storage not supported.")


def extract_article_inline_media_file_names(
    html: str,
    *,
    article_id: int,
    author_id: int,
) -> set[str]:
    allowed_prefix = f"articles/uploads/{author_id}/{article_id}/"

    soup = BeautifulSoup(html or "", "html.parser")
    file_names: set[str] = set()

    for img in soup.find_all("img"):
        src = img.get("src")
        file_name = _get_article_media_file_name_from_src(
            src if isinstance(src, str) else None
        )

        if file_name and file_name.startswith(allowed_prefix):
            file_names.add(file_name)

    return file_names


def _get_article_media_file_name_from_src(src: str | None) -> str | None:
    if not src:
        return None

    parsed = urlparse(src.strip())

    if parsed.scheme in {"data", "blob", "javascript"}:
        return None

    path = unquote(parsed.path or "")

    if "\x00" in path or ".." in path.split("/"):
        return None

    marker = "/articles/uploads/"
    if marker not in path:
        return None

    return path[path.index("articles/uploads/") :]


def _delete_local_filesystem_media(
    article_media_dir: str, article_id: int, storage: FileSystemStorage
) -> None:
    if not isinstance(storage, FileSystemStorage):
        raise ImproperlyConfigured("Unexpected media storage backend.")

    local_path = os.path.join(storage.location, article_media_dir)
    media_root = os.path.realpath(settings.MEDIA_ROOT)

    if not os.path.commonpath([media_root, os.path.realpath(local_path)]) == media_root:
        logger.error(
            "Attempted to delete a path ('%s') outside MEDIA_ROOT ('%s').",
            local_path,
            media_root,
        )
        return
    if not os.path.exists(local_path):
        logger.info(
            "Local media directory %s does not exist for article %s.",
            local_path,
            article_id,
        )
        return

    try:
        shutil.rmtree(local_path)
        logger.info(
            "Successfully batch-deleted local files for article %s.", article_id
        )
    except FileNotFoundError as e:
        logger.warning("Directory or file %s does not exist: %s.", local_path, str(e))
    except OSError as e:
        logger.error(
            "Failed to delete local media (%s) for article %s: %s.",
            local_path,
            article_id,
            str(e),
        )
        raise

    _delete_author_media_dir(os.path.dirname(local_path))


def _delete_s3_media(
    article_media_dir: str, article_id: int, storage: S3Boto3Storage
) -> None:
    if not isinstance(storage, S3Boto3Storage):
        raise ImproperlyConfigured("Unexpected media storage backend.")

    posix_media_dir = PurePosixPath(*PurePath(article_media_dir).parts)
    try:
        _, file_names = storage.listdir(posix_media_dir)
    except (SuspiciousFileOperation, OSError, BotoCoreError, ClientError):
        logger.exception(
            "Failed to list S3 directory %s for article %s.",
            posix_media_dir,
            article_id,
        )
        raise

    if not file_names:
        logger.info(
            "No S3 files to delete in %s for article %s.", posix_media_dir, article_id
        )
        return

    s3_client = storage.connection.meta.client
    keys = [{"Key": posixpath.join(posix_media_dir, name)} for name in file_names]

    for batch_number, i in enumerate(
        range(0, len(keys), MAX_S3_DELETE_BATCH_SIZE), start=1
    ):
        try:
            s3_client.delete_objects(
                Bucket=storage.bucket_name,
                Delete={"Objects": keys[i : i + MAX_S3_DELETE_BATCH_SIZE]},
            )
            logger.info(
                "Successfully deleted media (batch %s) for article %s.",
                batch_number,
                article_id,
            )
        except (SuspiciousFileOperation, OSError, BotoCoreError, ClientError):
            logger.exception(
                "Failed to delete media (batch %s) for article %s.",
                batch_number,
                article_id,
            )
            raise


def _delete_author_media_dir(author_dir: str):
    try:
        if os.path.isdir(author_dir) and not os.listdir(author_dir):
            os.rmdir(author_dir)
            logger.info("Removed empty author media folder: %s", author_dir)
    except OSError as e:
        logger.warning(
            "Failed to remove author media folder %s: %s", author_dir, str(e)
        )
