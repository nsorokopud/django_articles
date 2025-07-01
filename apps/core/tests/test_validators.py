from io import BytesIO
from unittest.mock import patch

import magic
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from config.settings import MAX_UPLOAD_FILE_SIZE
from core.exceptions import InvalidUpload
from core.validators import validate_uploaded_file


class TestValidateUploadedFile(SimpleTestCase):
    def test_file_without_name(self):
        file = BytesIO(b"content")
        with self.assertRaises(InvalidUpload) as context:
            validate_uploaded_file(file)
        self.assertEqual(str(context.exception), "Uploaded file must have a name.")

    def test_unsupported_extension(self):
        file = SimpleUploadedFile(
            "file.exe", b"data", content_type="application/octet-stream"
        )
        with self.assertRaises(InvalidUpload) as context:
            validate_uploaded_file(file)
        self.assertEqual(str(context.exception), "Unsupported file extension: exe.")

    def test_unseekable_file(self):
        file = SimpleUploadedFile(
            "file.jpeg", b"data", content_type="application/octet-stream"
        )
        file.seekable = lambda: False
        with self.assertRaises(InvalidUpload) as context:
            validate_uploaded_file(file)
        self.assertEqual(str(context.exception), "Uploaded file must be seekable.")

    def test_too_large_file(self):
        file_size = MAX_UPLOAD_FILE_SIZE + 1
        file = SimpleUploadedFile(
            "file.jpeg", b"a" * (file_size), content_type="text/plain"
        )
        with self.assertRaises(InvalidUpload) as context:
            validate_uploaded_file(file)
        self.assertEqual(
            str(context.exception),
            f"File too large ({file_size} bytes). "
            f"Max allowed: {MAX_UPLOAD_FILE_SIZE} bytes "
            f"({MAX_UPLOAD_FILE_SIZE / 1024**2:.1f} MB).",
        )

    @patch(
        "core.validators.magic.from_buffer",
        side_effect=magic.MagicException("Magic error"),
    )
    def test_magic_error(self, mock_magic):
        file = SimpleUploadedFile("file.jpg", b"fake jpg content")
        with self.assertRaises(InvalidUpload) as context:
            validate_uploaded_file(file)

        self.assertEqual(str(context.exception), "File type not recognized.")
        self.assertIsInstance(context.exception.__cause__, magic.MagicException)

    @patch("core.validators.magic.from_buffer", return_value="text/plain")
    def test_mime_mismatch(self, mock_magic):
        file = SimpleUploadedFile("file.jpg", b"fake jpg content")
        with self.assertRaises(InvalidUpload):
            validate_uploaded_file(file)

    @patch("core.validators.magic.from_buffer", return_value="image/jpeg")
    def test_valid_file(self, mock_magic):
        file = SimpleUploadedFile("file.jpg", b"jpg content", content_type="image/jpeg")
        validate_uploaded_file(file)
