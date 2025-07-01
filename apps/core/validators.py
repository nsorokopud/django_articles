import os
from typing import BinaryIO

import magic

from config.settings import ALLOWED_UPLOAD_FILE_TYPES, MAX_UPLOAD_FILE_SIZE

from .exceptions import InvalidUpload


def validate_uploaded_file(file: BinaryIO) -> None:
    if not hasattr(file, "name"):
        raise InvalidUpload("Uploaded file must have a name.")

    _, extension = os.path.splitext(file.name)
    extension = extension.lstrip(".").lower()
    if extension not in ALLOWED_UPLOAD_FILE_TYPES:
        raise InvalidUpload(f"Unsupported file extension: {extension}.")

    if not file.seekable():
        raise InvalidUpload("Uploaded file must be seekable.")

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_UPLOAD_FILE_SIZE:
        raise InvalidUpload(
            f"File too large ({file_size} bytes). "
            f"Max allowed: {MAX_UPLOAD_FILE_SIZE} bytes "
            f"({MAX_UPLOAD_FILE_SIZE / 1024**2:.1f} MB)."
        )

    try:
        mime_type = magic.from_buffer(file.read(1024), mime=True)
    except (magic.MagicException, TypeError, AttributeError) as e:
        raise InvalidUpload("File type not recognized.") from e
    finally:
        file.seek(0)

    expected_mime = ALLOWED_UPLOAD_FILE_TYPES[extension]
    if expected_mime != mime_type:
        raise InvalidUpload(
            "File content does not match its extension: "
            f"expected {expected_mime}, got {mime_type}."
        )
