from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

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
        )
        self.client = Client()
        self.url = reverse("attached-file-upload")

    @patch("articles.views.default_storage.url")
    @patch("articles.forms.validate_uploaded_file")
    @patch("articles.views.save_media_file_attached_to_article")
    def test_successful_upload(self, mock_save_media, mock_validate, mock_url):
        mock_save_media.return_value = ("path/to/file", f"/article/{self.article.id}/")
        mock_url.return_value = f"{self.article.id}-location"

        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")
        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "success",
                "data": {
                    "articleUrl": f"/articles/{self.article.slug}",
                    "location": mock_url.return_value,
                },
            },
        )

    def test_upload_without_login(self):
        file = SimpleUploadedFile("test.txt", b"hello")
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

    def test_missing_article_id(self):
        file = SimpleUploadedFile("test.jpg", b"hello")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, {"file": file}, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "Invalid or missing article ID",
            },
        )

    def test_invalid_article_id(self):
        file = SimpleUploadedFile("test.jpg", b"hello")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"file": file, "articleId": "abc"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "Invalid or missing article ID",
            },
        )

    def test_non_existent_article(self):
        file = SimpleUploadedFile("test.jpg", b"hello")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"file": file, "articleId": 9999},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "Page not found",
            },
        )

    def test_not_author(self):
        user = User.objects.create_user(username="user2", email="user2@test.com")

        self.client.force_login(user)
        file = SimpleUploadedFile("test.jpg", b"hello")
        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "No permission to edit this article",
            },
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
            {
                "status": "error",
                "message": "File is required.",
            },
        )

    @patch("articles.forms.AttachedFileUploadForm.clean_file")
    def test_invalid_file(self, mock_clean):
        mock_clean.side_effect = ValidationError("Some error")

        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")
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
                "message": "Some error",
            },
        )

    @patch(
        "articles.views.base.save_media_file_attached_to_article",
        side_effect=MediaSaveError("Media save error"),
    )
    @patch("articles.views.base.logger")
    @patch("articles.forms.validate_uploaded_file")
    def test_file_save_error(self, mock_validate, mock_logger, mock_save):
        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")

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

    @patch(
        "articles.views.base.save_media_file_attached_to_article",
        side_effect=ZeroDivisionError("Unexpected error"),
    )
    @patch("articles.views.base.logger")
    @patch("articles.forms.validate_uploaded_file")
    def test_unexpected_error(self, mock_validate, mock_logger, mock_save):
        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")

        self.client.raise_request_exception = False
        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        mock_save.assert_called_once()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(), {"status": "error", "message": "Internal server error"}
        )
