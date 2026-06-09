from io import BytesIO
from unittest.mock import patch

import magic
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from core.validators import validate_uploaded_file_type, validate_uploaded_image


TEST_ALLOWED_IMAGE_UPLOAD_FILE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

TEST_MAX_IMAGE_UPLOAD_FILE_SIZE = 5 * 1024 * 1024


class TestValidateUploadedImage(SimpleTestCase):
    @override_settings(
        ALLOWED_IMAGE_UPLOAD_FILE_TYPES=TEST_ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
        MAX_IMAGE_UPLOAD_FILE_SIZE=TEST_MAX_IMAGE_UPLOAD_FILE_SIZE,
    )
    @patch("core.validators.validate_uploaded_file_type")
    def test_delegates_to_validate_uploaded_file(self, mock_validate_uploaded_file):
        file = SimpleUploadedFile("file.jpg", b"jpg content", content_type="image/jpeg")

        validate_uploaded_image(file)

        mock_validate_uploaded_file.assert_called_once_with(
            file=file,
            allowed_file_types=TEST_ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
            max_file_size=TEST_MAX_IMAGE_UPLOAD_FILE_SIZE,
        )


class TestValidateUploadedFile(SimpleTestCase):
    def test_file_without_name(self):
        file = BytesIO(b"content")

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
            )

        self.assertEqual(
            context.exception.messages, ["Uploaded file must have a name."]
        )

    def test_file_without_extension(self):
        file = SimpleUploadedFile("file", b"data", content_type="image/jpeg")

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
            )

        self.assertEqual(
            context.exception.messages, ["Uploaded file must have an extension."]
        )

    def test_unsupported_extension(self):
        file = SimpleUploadedFile(
            "file.exe", b"data", content_type="application/octet-stream"
        )

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
            )

        self.assertEqual(
            context.exception.messages, ["Unsupported file extension: exe."]
        )

    def test_unseekable_file(self):
        file = SimpleUploadedFile(
            "file.jpeg", b"data", content_type="application/octet-stream"
        )
        file.seekable = lambda: False

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
            )

        self.assertEqual(
            context.exception.messages, ["Uploaded file must be seekable."]
        )

    def test_empty_file(self):
        file = SimpleUploadedFile("file.jpeg", b"", content_type="image/jpeg")

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
            )

        self.assertEqual(context.exception.messages, ["Uploaded file cannot be empty."])

    def test_too_large_file(self):
        max_file_size = settings.MAX_IMAGE_UPLOAD_FILE_SIZE
        file_size = max_file_size + 1
        file = SimpleUploadedFile(
            "file.jpeg",
            b"a" * file_size,
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=max_file_size,
            )

        self.assertEqual(
            context.exception.messages,
            [
                f"File too large ({file_size} bytes). "
                f"Max allowed: {max_file_size} bytes "
                f"({max_file_size / 1024**2:.1f} MB)."
            ],
        )

    @patch(
        "core.validators.magic.from_buffer",
        side_effect=magic.MagicException("Magic error"),
    )
    def test_magic_error(self, mock_magic):
        file = SimpleUploadedFile("file.jpg", b"fake jpg content")

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
            )

        self.assertEqual(context.exception.messages, ["File type not recognized."])
        self.assertIsInstance(context.exception.__cause__, magic.MagicException)
        mock_magic.assert_called_once_with(b"fake jpg content", mime=True)

    @patch("core.validators.magic.from_buffer", return_value="text/plain")
    def test_mime_mismatch(self, mock_magic):
        file = SimpleUploadedFile("file.jpg", b"fake jpg content")

        with self.assertRaises(ValidationError) as context:
            validate_uploaded_file_type(
                file=file,
                allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
                max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
            )

        self.assertEqual(
            context.exception.messages,
            [
                "File content does not match its extension: "
                "expected image/jpeg, got text/plain."
            ],
        )

    @patch("core.validators.magic.from_buffer", return_value="image/jpeg")
    def test_valid_file(self, mock_magic):
        file = SimpleUploadedFile("file.jpg", b"jpg content", content_type="image/jpeg")

        validate_uploaded_file_type(
            file=file,
            allowed_file_types=settings.ALLOWED_IMAGE_UPLOAD_FILE_TYPES,
            max_file_size=settings.MAX_IMAGE_UPLOAD_FILE_SIZE,
        )

        mock_magic.assert_called_once_with(b"jpg content", mime=True)
