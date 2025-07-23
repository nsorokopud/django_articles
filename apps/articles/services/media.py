import logging
import os
import posixpath
import shutil
from pathlib import PurePath, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage, default_storage
from django.utils.text import get_valid_filename
from storages.backends.s3boto3 import S3Boto3Storage

from config.settings import MEDIA_ROOT
from core.exceptions import MediaSaveError

from ..models import Article


logger = logging.getLogger(__name__)

MAX_S3_DELETE_BATCH_SIZE = 1000
ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE = "articles/uploads/{author_id}/{article_id}"


def save_media_file_attached_to_article(
    file: BinaryIO, article: Article
) -> tuple[str, str]:
    file_path = _build_safe_file_path(file, article)

    try:
        file_path = default_storage.save(file_path, file)
    except (
        OSError,
        SuspiciousFileOperation,
        S3UploadFailedError,
        ClientError,
    ) as e:
        logger.exception(
            "Failed to save file for article %s: %s (%s)",
            article.id,
            file_path,
            type(e).__name__,
        )
        raise MediaSaveError("Could not save the uploaded file.") from e

    return file_path, article.get_absolute_url()


def delete_media_files_attached_to_article(article_id: int, author_id: int) -> None:
    article_dir = ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE.format(
        author_id=author_id, article_id=article_id
    )

    if isinstance(default_storage, FileSystemStorage):
        _delete_local_filesystem_media(article_dir, article_id, default_storage)
    elif isinstance(default_storage, S3Boto3Storage):
        _delete_s3_media(article_dir, article_id, default_storage)
    else:
        raise ImproperlyConfigured("Media storage not supported.")


def _build_safe_file_path(file: BinaryIO, article: Article) -> str:
    base_name, extension = os.path.splitext(file.name)
    safe_base_name = get_valid_filename(base_name)
    filename = f"{safe_base_name}_{uuid4().hex}.{extension.lower()}"
    directory = posixpath.join(
        "articles", "uploads", str(article.author.id), str(article.id)
    )
    return posixpath.join(directory, filename)


def _delete_local_filesystem_media(
    article_media_dir: str, article_id: int, storage: FileSystemStorage
) -> None:
    if not isinstance(storage, FileSystemStorage):
        raise ImproperlyConfigured("Unexpected media storage backend.")

    local_path = os.path.join(storage.location, article_media_dir)
    media_root = os.path.realpath(MEDIA_ROOT)

    if not os.path.realpath(local_path).startswith(media_root):
        logger.error("Attempted to delete a path outside MEDIA_ROOT: %s.", local_path)
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
    except OSError:
        logger.exception(
            "Failed to delete local media (%s) for article %s.", local_path, article_id
        )
        raise


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
