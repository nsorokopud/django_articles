import os
from typing import BinaryIO

import magic
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_uploaded_image(file: BinaryIO) -> None:
    validate_uploaded_file_type(
        file=file,
        allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
        max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
    )


def validate_uploaded_file_type(
    *, file: BinaryIO, allowed_file_types: dict[str, str], max_file_size: int
) -> None:
    if not hasattr(file, "name"):
        raise ValidationError("Uploaded file must have a name.")

    _, extension = os.path.splitext(file.name)
    extension = extension.lstrip(".").lower()

    if not extension:
        raise ValidationError("Uploaded file must have an extension.")

    if extension not in allowed_file_types:
        raise ValidationError(f"Unsupported file extension: {extension}.")

    if not file.seekable():
        raise ValidationError("Uploaded file must be seekable.")

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size <= 0:
        raise ValidationError("Uploaded file cannot be empty.")

    if file_size > max_file_size:
        raise ValidationError(
            f"File too large ({file_size} bytes). "
            f"Max allowed: {max_file_size} bytes "
            f"({max_file_size / 1024**2:.1f} MB)."
        )

    try:
        mime_type = magic.from_buffer(file.read(2048), mime=True)
    except (magic.MagicException, TypeError, AttributeError) as e:
        raise ValidationError("File type not recognized.") from e
    finally:
        file.seek(0)

    expected_mime = allowed_file_types[extension]

    if mime_type != expected_mime:
        raise ValidationError(
            "File content does not match its extension: "
            f"expected {expected_mime}, got {mime_type}."
        )
