from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from articles.models import Article
from core.exceptions import MediaSaveError
from users.models import User


class TestAttachedFileUploadView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="text1",
            content="content1",
            content_text="content1",
        )
        self.client = Client()
        self.url = reverse("attached-file-upload")

    @patch("articles.views.uploads.default_storage.url")
    @patch("articles.views.uploads.save_article_inline_media_file")
    @patch("core.validators.magic.from_buffer", return_value="image/jpeg")
    def test_successful_upload(self, mock_magic, mock_save_media, mock_url):
        mock_save_media.return_value = "path/to/file"
        mock_url.return_value = f"{self.article.id}-location"

        self.client.force_login(self.user)
        file = SimpleUploadedFile(
            "test.jpg", b"fake jpg content", content_type="image/jpeg"
        )

        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"location": mock_url.return_value}},
        )
        mock_save_media.assert_called_once()
        mock_url.assert_called_once_with("path/to/file")

    def test_upload_without_login(self):
        file = SimpleUploadedFile("test.jpg", b"hello", content_type="image/jpeg")

        response = self.client.post(
            self.url,
            {"file": file, "articleId": "123"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('attached-file-upload')}",
            302,
            200,
        )

    def test_cannot_upload_to_published_article(self):
        self.article.status = "published"
        self.article.published_at = timezone.now()
        self.article.save(update_fields=["status", "published_at"])

        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello", content_type="image/jpeg")

        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "This article cannot be edited."},
        )

    def test_missing_article_id(self):
        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello", content_type="image/jpeg")

        response = self.client.post(
            self.url, {"file": file}, headers={"X-Requested-With": "XMLHttpRequest"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "Invalid or missing article ID"},
        )

    def test_invalid_article_id(self):
        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello", content_type="image/jpeg")

        response = self.client.post(
            self.url,
            {"file": file, "articleId": "abc"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "Invalid or missing article ID"},
        )

    def test_non_existent_article(self):
        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello", content_type="image/jpeg")

        response = self.client.post(
            self.url,
            {"file": file, "articleId": 9999},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "Page not found"},
        )

    def test_not_author(self):
        user = User.objects.create_user(username="user2", email="user2@test.com")

        self.client.force_login(user)
        file = SimpleUploadedFile("test.jpg", b"hello", content_type="image/jpeg")

        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "No permission to edit this article."},
        )

    def test_no_file(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "File is required."},
        )

    @patch("core.validators.magic.from_buffer", return_value="text/plain")
    def test_invalid_file(self, mock_magic):
        self.client.force_login(self.user)
        file = SimpleUploadedFile(
            "test.jpg", b"not actually a jpg", content_type="image/jpeg"
        )

        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": (
                    "File content does not match its extension: "
                    "expected image/jpeg, got text/plain."
                ),
            },
        )

    @patch(
        "articles.views.uploads.save_article_inline_media_file",
        side_effect=MediaSaveError("Media save error"),
    )
    @patch("articles.views.uploads.logger")
    @patch("core.validators.magic.from_buffer", return_value="image/jpeg")
    def test_file_save_error(self, mock_magic, mock_logger, mock_save):
        self.client.force_login(self.user)
        file = SimpleUploadedFile(
            "test.jpg", b"fake jpg content", content_type="image/jpeg"
        )

        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        mock_save.assert_called_once()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(), {"status": "error", "message": "File saving error"}
        )
        mock_logger.exception.assert_called_once_with(
            "Error while saving uploaded file."
        )
