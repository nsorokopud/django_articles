import logging
import os
import posixpath
from typing import BinaryIO
from uuid import uuid4

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename

from core.exceptions import MediaSaveError

from ..models import Article


logger = logging.getLogger("default_logger")


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


def delete_media_files_attached_to_article(article: Article) -> None:
    article_dir = os.path.join(
        "articles", "uploads", article.author.username, str(article.id)
    )
    if default_storage.exists(article_dir):
        for file in default_storage.listdir(article_dir)[1]:
            default_storage.delete(os.path.join(article_dir, file))
        default_storage.delete(article_dir)


def _build_safe_file_path(file: BinaryIO, article: Article) -> str:
    base_name, extension = os.path.splitext(file.name)
    safe_base_name = get_valid_filename(base_name)
    filename = f"{safe_base_name}_{uuid4().hex}.{extension.lower()}"
    directory = posixpath.join(
        "articles", "uploads", str(article.author.id), str(article.id)
    )
    return posixpath.join(directory, filename)
