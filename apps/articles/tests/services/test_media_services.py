import os
from unittest.mock import ANY, call, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from articles.models import Article
from articles.services import (
    delete_media_files_attached_to_article,
    save_media_file_attached_to_article,
)
from core.exceptions import MediaSaveError
from users.models import User


class TestDeleteMediaFilesAttachedToArticle(TestCase):
    def test_delete_media_files_attached_to_article(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        a = Article.objects.create(
            title="a1",
            slug="a1",
            author=user,
            preview_text="text1",
            content="content1",
        )
        directory = f"articles/uploads/{user.username}/{a.id}"

        with (
            patch("articles.services.default_storage.exists", return_value=True),
            patch(
                "articles.services.default_storage.listdir",
                return_value=[[directory], ["file1", "file2"]],
            ),
            patch("articles.services.default_storage.delete") as delete_mock,
        ):

            delete_media_files_attached_to_article(a)
            delete_mock.assert_has_calls(
                [
                    call(os.path.join(directory, "file1")),
                    call(os.path.join(directory, "file2")),
                    call(directory),
                ],
                any_order=False,
            )


class TestSaveMediaFileAttachedToArticle(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester")
        self.article = Article.objects.create(
            title="a1", slug="a1", content="content", author=self.user
        )

    @patch("articles.services.logger")
    @patch("articles.services.default_storage.save")
    def test_successful_file_save(self, mock_save, mock_logger):
        file = SimpleUploadedFile("img.jpeg", b"jpeg data", content_type="image/jpeg")
        mock_save.return_value = "articles/uploads/img.jpeg"
        file_path, url = save_media_file_attached_to_article(file, self.article)
        self.assertEqual(file_path, "articles/uploads/img.jpeg")
        self.assertEqual(url, self.article.get_absolute_url())

        mock_save.assert_called_once()
        path_arg_value = mock_save.call_args_list[0][0][0]
        *_, file_name = path_arg_value.split("/")
        folder_path = path_arg_value.rsplit("/", 1)[0]
        file_base, file_ext = file_name.rsplit(".", 1)
        self.assertEqual(
            folder_path, f"articles/uploads/{self.user.username}/{self.article.id}"
        )
        self.assertIn("img", file_base)
        self.assertEqual(file_ext, "jpeg")

        mock_logger.warning.assert_not_called()
        mock_logger.exception.assert_not_called()

    @patch("articles.services.media.logger")
    @patch("articles.services.media.default_storage.save")
    def test_storage_save_failure(self, mock_save, mock_logger):
        mock_save.side_effect = OSError("Disk error")
        file = SimpleUploadedFile("file.jpeg", b"test", content_type="image/jpeg")

        with self.assertRaises(MediaSaveError) as context:
            save_media_file_attached_to_article(file, self.article)

        self.assertEqual(str(context.exception), "Could not save the uploaded file.")
        self.assertIsInstance(context.exception.__cause__, OSError)

        mock_logger.exception.assert_called_once_with(
            "Failed to save file for article %s: %s (%s)",
            self.article.id,
            ANY,
            "OSError",
        )
        path_arg_value = mock_logger.exception.call_args_list[0][0][2]
        *_, file_name = path_arg_value.split("/")
        folder_path = path_arg_value.rsplit("/", 1)[0]
        file_base, file_ext = file_name.rsplit(".", 1)
        self.assertEqual(
            folder_path, f"articles/uploads/{self.user.username}/{self.article.id}"
        )
        self.assertIn("file", file_base)
        self.assertEqual(file_ext, "jpeg")
