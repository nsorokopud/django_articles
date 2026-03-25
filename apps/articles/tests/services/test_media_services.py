import os
import shutil
import tempfile
from pathlib import PurePosixPath
from unittest.mock import ANY, Mock, call, patch

from botocore.exceptions import ClientError
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from storages.backends.s3boto3 import S3Boto3Storage

from articles.models import Article
from articles.services.media import (
    ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE,
    MAX_S3_DELETE_BATCH_SIZE,
    _delete_author_media_dir,
    _delete_local_filesystem_media,
    _delete_s3_media,
    delete_media_files_attached_to_article,
    save_media_file_attached_to_article,
)
from core.exceptions import MediaSaveError
from users.models import User


class TestDeleteMediaFilesAttachedToArticle(SimpleTestCase):
    def setUp(self):
        self.article_id = 123
        self.author_id = 1
        self.article_dir = ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE.format(
            author_id=self.author_id, article_id=self.article_id
        )

    @override_settings(
        STORAGES={
            "default": {"BACKEND": ("django.core.files.storage.FileSystemStorage")}
        }
    )
    def test_local_fs_storage(self):
        self.assertIsInstance(default_storage, FileSystemStorage)

        with patch(
            "articles.services.media._delete_local_filesystem_media"
        ) as mock_delete:
            delete_media_files_attached_to_article(self.article_id, self.author_id)

        mock_delete.assert_called_once_with(
            self.article_dir, self.article_id, default_storage
        )

    @override_settings(
        STORAGES={"default": {"BACKEND": ("storages.backends.s3boto3.S3Boto3Storage")}}
    )
    def test_s3_storage(self):
        with patch("articles.services.media._delete_s3_media") as mock_delete:
            delete_media_files_attached_to_article(self.article_id, self.author_id)

        mock_delete.assert_called_once_with(
            self.article_dir, self.article_id, default_storage
        )

    @override_settings(
        STORAGES={"default": {"BACKEND": ("django.core.files.storage.InMemoryStorage")}}
    )
    def test_unsupported_storage(self):
        with (
            patch(
                "articles.services.media._delete_local_filesystem_media"
            ) as mock_delete_local,
            patch("articles.services.media._delete_s3_media") as mock_delete_s3,
            self.assertRaises(ImproperlyConfigured) as context,
        ):
            delete_media_files_attached_to_article(self.article_id, self.author_id)

        self.assertEqual(str(context.exception), "Media storage not supported.")
        mock_delete_local.assert_not_called()
        mock_delete_s3.assert_not_called()


class TestDeleteS3Media(SimpleTestCase):
    def setUp(self):
        self.article_id = 123
        self.article_dir = "media/articles/1/123"
        self.posix_dir = PurePosixPath("media/articles/1/123")

        self.storage = Mock(spec=S3Boto3Storage)
        self.storage.bucket_name = "test-bucket"
        self.s3_client = self.storage.connection.meta.client = Mock()

    @patch("articles.services.media.logger")
    def test_single_batch(self, mock_logger):
        self.storage.listdir.return_value = ([], ["file1.jpg", "file2.png"])

        _delete_s3_media(self.article_dir, self.article_id, self.storage)

        expected_keys = [
            {"Key": f"{self.posix_dir}/file1.jpg"},
            {"Key": f"{self.posix_dir}/file2.png"},
        ]

        self.s3_client.delete_objects.assert_called_once_with(
            Bucket="test-bucket",
            Delete={"Objects": expected_keys},
        )
        mock_logger.info.assert_called_once_with(
            "Successfully deleted media (batch %s) for article %s.",
            1,
            self.article_id,
        )

    @patch("articles.services.media.logger")
    def test_multiple_batches(self, mock_logger):
        file_names = [f"img_{i}.jpg" for i in range(MAX_S3_DELETE_BATCH_SIZE + 10)]
        self.storage.listdir.return_value = ([], file_names)

        _delete_s3_media(self.article_dir, self.article_id, self.storage)
        self.assertEqual(self.s3_client.delete_objects.call_count, 2)
        call_1_keys = [
            {"Key": f"{self.posix_dir}/img_{i}.jpg"}
            for i in range(MAX_S3_DELETE_BATCH_SIZE)
        ]
        call_2_keys = [
            {"Key": f"{self.posix_dir}/img_{i}.jpg"}
            for i in range(MAX_S3_DELETE_BATCH_SIZE, MAX_S3_DELETE_BATCH_SIZE + 10)
        ]
        self.assertEqual(
            self.s3_client.delete_objects.call_args_list,
            [
                call(Bucket="test-bucket", Delete={"Objects": call_1_keys}),
                call(Bucket="test-bucket", Delete={"Objects": call_2_keys}),
            ],
        )
        self.assertEqual(
            mock_logger.info.call_args_list,
            [
                call(
                    "Successfully deleted media (batch %s) for article %s.",
                    1,
                    self.article_id,
                ),
                call(
                    "Successfully deleted media (batch %s) for article %s.",
                    2,
                    self.article_id,
                ),
            ],
        )

    def test_no_files_to_delete(self):
        self.storage.listdir.return_value = ([], [])

        with patch("articles.services.media.logger") as mock_logger:
            _delete_s3_media(self.article_dir, self.article_id, self.storage)

        self.s3_client.delete_objects.assert_not_called()
        mock_logger.info.assert_called_with(
            "No S3 files to delete in %s for article %s.",
            self.posix_dir,
            self.article_id,
        )

    def test_unsupported_storage(self):
        with self.assertRaises(ImproperlyConfigured):
            _delete_s3_media(
                self.article_dir, self.article_id, storage=FileSystemStorage()
            )

    def test_listdir_exception(self):
        self.storage.listdir.side_effect = ClientError({"Error": {}}, "ListObjectsV2")

        with (
            self.assertRaises(ClientError),
            patch("articles.services.media.logger") as mock_logger,
        ):
            _delete_s3_media(self.article_dir, self.article_id, self.storage)

        mock_logger.exception.assert_called_with(
            "Failed to list S3 directory %s for article %s.",
            self.posix_dir,
            self.article_id,
        )

    @patch("articles.services.media.logger")
    def test_delete_objects_exception(self, mock_logger):
        self.storage.listdir.return_value = [[], ["file1", "file2"]]
        self.storage.connection.meta.client.delete_objects.side_effect = OSError(
            "Error"
        )

        with self.assertRaises(OSError):
            _delete_s3_media(self.article_dir, self.article_id, self.storage)

        mock_logger.exception.assert_called_with(
            "Failed to delete media (batch %s) for article %s.", 1, self.article_id
        )


class TestDeleteLocalFileSystemMedia(SimpleTestCase):
    def setUp(self):
        self.temp_media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_media_root)

        self.mock_media_root = patch(
            "articles.services.media.MEDIA_ROOT", self.temp_media_root
        )
        self.mock_media_root.start()
        self.addCleanup(self.mock_media_root.stop)

        self.storage = FileSystemStorage(location=self.temp_media_root)

        self.author_id = 42
        self.article_id = 101
        self.author_path = os.path.join(self.temp_media_root, str(self.author_id))
        self.article_media_dir = f"{self.author_id}/{self.article_id}"
        self.article_path = os.path.join(self.temp_media_root, self.article_media_dir)
        os.makedirs(self.article_path)

        self.file_path = os.path.join(self.article_path, "file1.txt")
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("content")

    @patch("articles.services.media.logger")
    @patch("articles.services.media._delete_author_media_dir")
    @patch("articles.services.media.shutil.rmtree")
    def test_wrong_storage_type(self, mock_rmtree, mock_delete, mock_logger):
        with self.assertRaises(ImproperlyConfigured):
            _delete_local_filesystem_media(
                self.article_media_dir, self.article_id, storage=S3Boto3Storage()
            )

        mock_rmtree.assert_not_called()
        mock_delete.assert_not_called()
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()

    @patch("articles.services.media.logger")
    @patch("articles.services.media._delete_author_media_dir")
    def test_path_outside_media_root(self, mock_delete, mock_logger):
        invalid_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, invalid_root)
        storage = FileSystemStorage(location=invalid_root)
        article_path = os.path.join(storage.location, self.article_media_dir)
        os.makedirs(article_path)
        file = os.path.join(self.article_path, "file1.txt")
        with open(file, "w", encoding="utf-8") as f:
            f.write("content")

        self.assertTrue(os.path.exists(file))

        _delete_local_filesystem_media(self.article_media_dir, self.article_id, storage)

        self.assertTrue(os.path.exists(file))
        mock_delete.assert_not_called()
        mock_logger.error.assert_called_once_with(
            "Attempted to delete a path ('%s') outside MEDIA_ROOT ('%s').",
            article_path,
            self.temp_media_root,
        )
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()

    @patch("articles.services.media.logger")
    @patch("articles.services.media._delete_author_media_dir")
    def test_article_directory_missing(self, mock_delete, mock_logger):
        shutil.rmtree(self.article_path)
        self.assertFalse(os.path.exists(self.article_path))

        _delete_local_filesystem_media(
            self.article_media_dir, self.article_id, self.storage
        )

        mock_delete.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Local media directory %s does not exist for article %s.",
            self.article_path,
            self.article_id,
        )

        self.assertTrue(os.path.exists(self.author_path))

    @patch("articles.services.media.logger")
    @patch("articles.services.media._delete_author_media_dir")
    @patch(
        "articles.services.media.shutil.rmtree",
        side_effect=FileNotFoundError("Not found"),
    )
    def test_file_not_found_when_deleting(self, mock_rmtree, mock_delete, mock_logger):
        _delete_local_filesystem_media(
            self.article_media_dir, self.article_id, self.storage
        )
        mock_delete.assert_called_once_with(self.author_path)
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_called_once_with(
            "Directory or file %s does not exist: %s.", self.article_path, "Not found"
        )
        mock_logger.error.assert_not_called()
        self.assertTrue(os.path.exists(self.file_path))

    @patch("articles.services.media.logger")
    @patch("articles.services.media._delete_author_media_dir")
    @patch(
        "articles.services.media.shutil.rmtree",
        side_effect=OSError("OS error"),
    )
    def test_os_error_when_deleting(self, mock_rmtree, mock_delete, mock_logger):
        with self.assertRaises(OSError) as context:
            _delete_local_filesystem_media(
                self.article_media_dir, self.article_id, self.storage
            )

        self.assertEqual(str(context.exception), "OS error")
        mock_logger.delete.assert_not_called()
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_called_once_with(
            "Failed to delete local media (%s) for article %s: %s.",
            self.article_path,
            self.article_id,
            str(mock_rmtree.side_effect),
        )
        self.assertTrue(os.path.exists(self.article_path))

    @patch("articles.services.media.logger")
    @patch("articles.services.media._delete_author_media_dir")
    def test_deletes_article_media_dir(self, mock_delete, mock_logger):
        self.assertTrue(os.path.exists(self.file_path))

        _delete_local_filesystem_media(
            self.article_media_dir, self.article_id, self.storage
        )

        self.assertFalse(os.path.exists(self.article_path))
        mock_delete.assert_called_once_with(self.author_path)
        mock_logger.error.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Successfully batch-deleted local files for article %s.",
            self.article_id,
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
            folder_path, f"articles/uploads/{self.user.id}/{self.article.id}"
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
            folder_path, f"articles/uploads/{self.user.id}/{self.article.id}"
        )
        self.assertIn("file", file_base)
        self.assertEqual(file_ext, "jpeg")


class TestDeleteAuthorMediaDir(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(
            lambda x: shutil.rmtree(x) if os.path.exists(x) else ..., self.dir
        )

    @patch("articles.services.media.logger")
    def test_not_dir(self, mock_logger):
        path = "not-dir"
        self.assertFalse(os.path.exists(path))

        _delete_author_media_dir(path)
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        self.assertTrue(os.path.exists(self.dir))

    @patch("articles.services.media.logger")
    def test_empty_dir(self, mock_logger):
        self.assertTrue(os.path.exists(self.dir))

        _delete_author_media_dir(self.dir)
        mock_logger.info.assert_called_once_with(
            "Removed empty author media folder: %s", self.dir
        )
        mock_logger.warning.assert_not_called()
        self.assertFalse(os.path.exists(self.dir))

    @patch("articles.services.media.logger")
    def test_non_empty_dir(self, mock_logger):
        self.file_path = os.path.join(self.dir, "file1.txt")
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("content")

        self.assertTrue(os.path.exists(self.file_path))

        _delete_author_media_dir(self.dir)
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        self.assertTrue(os.path.exists(self.file_path))

    @patch("articles.services.media.logger")
    @patch("articles.services.media.os.rmdir", side_effect=OSError("OS error"))
    def test_os_error_when_deleting(self, mock_rmdir, mock_logger):
        _delete_author_media_dir(self.dir)
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_called_once_with(
            "Failed to remove author media folder %s: %s",
            self.dir,
            str(mock_rmdir.side_effect),
        )
