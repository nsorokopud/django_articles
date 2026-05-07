import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import PurePosixPath
from unittest.mock import Mock, call, patch

from botocore.exceptions import BotoCoreError, ClientError
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from storages.backends.s3boto3 import S3Boto3Storage

from articles.models import Article, ArticleMedia
from articles.services.media import (
    ARTICLE_MEDIA_UNUSED_GRACE_PERIOD,
    ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE,
    MAX_S3_DELETE_BATCH_SIZE,
    _delete_author_media_dir,
    _delete_local_filesystem_media,
    _delete_s3_media,
    cleanup_unused_article_inline_media,
    delete_article_inline_media_files,
    delete_article_media_files,
    delete_article_preview_image_file,
    extract_article_inline_media_file_names,
    save_article_inline_media_file,
    sync_article_inline_media_references,
)
from core.exceptions import MediaSaveError
from users.models import User


class TestDeleteArticlePreviewImageFile(SimpleTestCase):
    def test_returns_without_deleting_when_file_name_is_empty(self):
        with patch("articles.services.media.default_storage.delete") as mock_delete:
            delete_article_preview_image_file("")

        mock_delete.assert_not_called()

    def test_deletes_preview_image_file(self):
        with patch("articles.services.media.default_storage.delete") as mock_delete:
            delete_article_preview_image_file("articles/preview_images/1/test.jpg")

        mock_delete.assert_called_once_with("articles/preview_images/1/test.jpg")

    def test_logs_and_swallows_expected_storage_exceptions(self):
        file_name = "articles/preview_images/1/test.jpg"

        exceptions = [
            OSError("storage failed"),
            BotoCoreError(),
            ClientError(
                error_response={
                    "Error": {"Code": "AccessDenied", "Message": "Access denied"}
                },
                operation_name="DeleteObject",
            ),
            SuspiciousFileOperation("bad path"),
        ]

        for exception in exceptions:
            with self.subTest(exception=type(exception).__name__):
                with (
                    patch(
                        "articles.services.media.default_storage.delete",
                        side_effect=exception,
                    ) as mock_delete,
                    patch("articles.services.media.logger") as mock_logger,
                ):
                    delete_article_preview_image_file(file_name)

                mock_delete.assert_called_once_with(file_name)
                mock_logger.exception.assert_called_once_with(
                    "Failed to delete old article preview image: %s", file_name
                )


class TestDeleteArticleMediaFiles(SimpleTestCase):
    def setUp(self):
        self.article_id = 123
        self.author_id = 1
        self.preview_image_name = "articles/preview_images/preview.jpg"

    @patch("articles.services.media.default_storage.delete")
    @patch("articles.services.media.delete_article_inline_media_files")
    def test_deletes_inline_media_and_preview_image(
        self, mock_delete_inline_media, mock_storage_delete
    ):
        delete_article_media_files(
            article_id=self.article_id,
            author_id=self.author_id,
            preview_image_name=self.preview_image_name,
        )

        mock_delete_inline_media.assert_called_once_with(
            article_id=self.article_id, author_id=self.author_id
        )
        mock_storage_delete.assert_called_once_with(self.preview_image_name)

    @patch("articles.services.media.default_storage.delete")
    @patch("articles.services.media.delete_article_inline_media_files")
    def test_deletes_only_inline_media_when_preview_image_missing(
        self, mock_delete_inline_media, mock_storage_delete
    ):
        delete_article_media_files(
            article_id=self.article_id, author_id=self.author_id, preview_image_name=""
        )

        mock_delete_inline_media.assert_called_once_with(
            article_id=self.article_id, author_id=self.author_id
        )
        mock_storage_delete.assert_not_called()

    @patch("articles.services.media.logger")
    @patch("articles.services.media.default_storage.delete")
    @patch("articles.services.media.delete_article_inline_media_files")
    def test_preview_image_delete_error_is_logged_and_raised(
        self, mock_delete_inline_media, mock_storage_delete, mock_logger
    ):
        mock_storage_delete.side_effect = OSError("delete failed")

        with self.assertRaises(OSError):
            delete_article_media_files(
                article_id=self.article_id,
                author_id=self.author_id,
                preview_image_name=self.preview_image_name,
            )

        mock_delete_inline_media.assert_called_once_with(
            article_id=self.article_id, author_id=self.author_id
        )
        mock_storage_delete.assert_called_once_with(self.preview_image_name)
        mock_logger.exception.assert_called_once_with(
            "Failed to delete preview image %s for article %s.",
            self.preview_image_name,
            self.article_id,
        )


class TestSaveArticleInlineMediaFile(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester")
        self.article = Article.objects.create(
            title="a1", slug="a1", content="content", author=self.user
        )

    def test_successful_file_save_creates_article_media(self):
        file = SimpleUploadedFile("img.jpeg", b"jpeg data", content_type="image/jpeg")

        before = timezone.now()
        file_path = save_article_inline_media_file(file, self.article)
        after = timezone.now()

        media = ArticleMedia.objects.get(article=self.article)

        self.assertEqual(file_path, media.file.name)
        self.assertGreaterEqual(media.unreferenced_at, before)
        self.assertLessEqual(media.unreferenced_at, after)

        folder_path = file_path.rsplit("/", 1)[0]
        file_name = file_path.rsplit("/", 1)[1]

        self.assertEqual(
            folder_path, f"articles/uploads/{self.user.id}/{self.article.id}"
        )
        self.assertNotIn("..", file_name)

        name, ext = file_name.rsplit(".", 1)
        self.assertEqual(ext, "jpeg")

        prefix, uuid_part = name.rsplit("_", 1)
        self.assertEqual(prefix, "img")
        self.assertEqual(len(uuid_part), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in uuid_part))

    @patch("articles.services.media.logger")
    @patch("articles.models.ArticleMedia.file.field.storage.save")
    def test_storage_save_failure(self, mock_save, mock_logger):
        mock_save.side_effect = OSError("Disk error")
        file = SimpleUploadedFile("file.jpeg", b"test", content_type="image/jpeg")

        with self.assertRaises(MediaSaveError) as context:
            save_article_inline_media_file(file, self.article)

        self.assertEqual(str(context.exception), "Could not save the uploaded file.")
        self.assertIsInstance(context.exception.__cause__, OSError)

        mock_logger.exception.assert_called_once_with(
            "Failed to save media for article %s: %s", self.article.id, "OSError"
        )
        self.assertFalse(ArticleMedia.objects.filter(article=self.article).exists())

    @patch("articles.services.media.logger")
    @patch("articles.services.media.default_storage.delete")
    @patch("articles.services.media.ArticleMedia.save")
    def test_db_save_failure_deletes_uploaded_file(
        self, mock_media_save, mock_delete, mock_logger
    ):
        mock_media_save.side_effect = OSError("DB error")
        file = SimpleUploadedFile("file.jpeg", b"test", content_type="image/jpeg")

        with self.assertRaises(MediaSaveError):
            save_article_inline_media_file(file, self.article)

        mock_delete.assert_called_once()
        self.assertFalse(ArticleMedia.objects.filter(article=self.article).exists())

        deleted_path = mock_delete.call_args.args[0]
        self.assertTrue(
            deleted_path.startswith(
                f"articles/uploads/{self.user.id}/{self.article.id}/file_"
            )
        )
        self.assertTrue(deleted_path.endswith(".jpeg"))


class TestSyncArticleInlineMediaReferences(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester")
        self.article = Article.objects.create(
            title="a1", slug="a1", content="content", author=self.user
        )

    def test_marks_referenced_media_as_used(self):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/img.jpeg",
            unreferenced_at=timezone.now(),
        )
        self.article.content = (
            f'<p>Hello</p><img src="/media/articles/uploads/'
            f'{self.user.id}/{self.article.id}/img.jpeg">'
        )

        sync_article_inline_media_references(article=self.article)

        media.refresh_from_db()
        self.assertIsNone(media.unreferenced_at)

    def test_marks_removed_media_as_unreferenced(self):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/img.jpeg",
            unreferenced_at=None,
        )
        self.article.content = "<p>No image</p>"

        before = timezone.now()
        sync_article_inline_media_references(article=self.article)
        after = timezone.now()

        media.refresh_from_db()
        self.assertIsNotNone(media.unreferenced_at)
        self.assertGreaterEqual(media.unreferenced_at, before)
        self.assertLessEqual(media.unreferenced_at, after)

    def test_ignores_media_from_other_article(self):
        other_article = Article.objects.create(
            title="a2", slug="a2", content="content", author=self.user
        )
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/img.jpeg",
            unreferenced_at=timezone.now(),
        )
        self.article.content = (
            f'<img src="/media/articles/uploads/'
            f'{self.user.id}/{other_article.id}/img.jpeg">'
        )

        sync_article_inline_media_references(article=self.article)

        media.refresh_from_db()
        self.assertIsNotNone(media.unreferenced_at)


class TestCleanupUnusedArticleInlineMedia(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester")
        self.article = Article.objects.create(
            title="a1", slug="a1", content="content", author=self.user
        )

    @patch("articles.services.media.default_storage.delete")
    def test_skips_media_if_no_longer_unreferenced(self, mock_delete):
        old_time = (
            timezone.now() - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD - timedelta(seconds=1)
        )
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/old.jpeg",
            unreferenced_at=old_time,
        )

        ArticleMedia.objects.filter(id=media.id).update(unreferenced_at=None)

        deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 0)
        mock_delete.assert_not_called()
        self.assertTrue(ArticleMedia.objects.filter(id=media.id).exists())

    @patch("articles.services.media.default_storage.delete")
    def test_deletes_old_unreferenced_media(self, mock_delete):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/old.jpeg",
            unreferenced_at=timezone.now()
            - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD
            - timedelta(seconds=1),
        )

        deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 1)
        mock_delete.assert_called_once_with(media.file.name)
        self.assertFalse(ArticleMedia.objects.filter(id=media.id).exists())

    @patch("articles.services.media.default_storage.delete")
    def test_keeps_recent_unreferenced_media(self, mock_delete):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/recent.jpeg",
            unreferenced_at=timezone.now(),
        )

        deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 0)
        mock_delete.assert_not_called()
        self.assertTrue(ArticleMedia.objects.filter(id=media.id).exists())

    @patch("articles.services.media.default_storage.delete")
    def test_keeps_referenced_media(self, mock_delete):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/used.jpeg",
            unreferenced_at=None,
        )

        deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 0)
        mock_delete.assert_not_called()
        self.assertTrue(ArticleMedia.objects.filter(id=media.id).exists())

    @patch("articles.services.media.logger")
    @patch("articles.services.media.default_storage.delete")
    def test_storage_delete_failure_deletes_db_row_and_logs_orphan(
        self, mock_delete, mock_logger
    ):
        mock_delete.side_effect = OSError("delete failed")
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/old.jpeg",
            unreferenced_at=timezone.now()
            - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD
            - timedelta(seconds=1),
        )

        deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 0)
        self.assertFalse(ArticleMedia.objects.filter(id=media.id).exists())

        mock_logger.exception.assert_called_once_with(
            "Deleted ArticleMedia row, but failed to delete storage file %s",
            media.file.name,
        )
        mock_logger.warning.assert_called_once_with(
            "Cleaned up %s ArticleMedia rows but only deleted %s storage files.", 1, 0
        )

    @patch("articles.services.media.logger")
    @patch("articles.services.media.default_storage.delete")
    def test_mixed_storage_delete_success_and_failure(self, mock_delete, mock_logger):
        old_time = (
            timezone.now() - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD - timedelta(seconds=1)
        )
        media_1 = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/1.jpeg",
            unreferenced_at=old_time,
        )
        media_2 = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/2.jpeg",
            unreferenced_at=old_time,
        )

        def delete_side_effect(file_name):
            if file_name == media_1.file.name:
                raise OSError("delete failed")

        mock_delete.side_effect = delete_side_effect

        deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 1)
        self.assertFalse(ArticleMedia.objects.filter(id=media_1.id).exists())
        self.assertFalse(ArticleMedia.objects.filter(id=media_2.id).exists())
        mock_logger.warning.assert_called_once_with(
            "Cleaned up %s ArticleMedia rows but only deleted %s storage files.", 2, 1
        )

    @patch("articles.services.media.default_storage.delete")
    def test_respects_batch_size(self, mock_delete):
        old_time = (
            timezone.now() - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD - timedelta(seconds=1)
        )
        media_1 = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/1.jpeg",
            unreferenced_at=old_time,
        )
        media_2 = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/2.jpeg",
            unreferenced_at=old_time,
        )

        deleted_count = cleanup_unused_article_inline_media(batch_size=1)

        self.assertEqual(deleted_count, 1)
        self.assertEqual(mock_delete.call_count, 1)
        self.assertEqual(ArticleMedia.objects.count(), 1)
        remaining_ids = set(ArticleMedia.objects.values_list("id", flat=True))
        self.assertIn(media_2.id, remaining_ids)
        self.assertNotIn(media_1.id, remaining_ids)


class TestExtractArticleInlineMediaFileNames(SimpleTestCase):
    @override_settings(
        MEDIA_URL="/media/",
        MEDIA_ALLOWED_ROOT_URLS=["https://cdn.test/media/"],
    )
    def test_extracts_matching_article_media_paths(self):
        html = (
            "<p>Hello</p>"
            '<img src="/media/articles/uploads/1/2/a.jpeg">'
            '<img src="https://cdn.test/media/articles/uploads/1/2/b.png">'
        )

        result = extract_article_inline_media_file_names(
            html, article_id=2, author_id=1
        )

        self.assertEqual(
            result, {"articles/uploads/1/2/a.jpeg", "articles/uploads/1/2/b.png"}
        )

    @override_settings(MEDIA_URL="/media/")
    def test_ignores_other_articles_and_authors(self):
        html = (
            '<img src="/media/articles/uploads/1/999/a.jpeg">'
            '<img src="/media/articles/uploads/999/2/b.jpeg">'
        )

        result = extract_article_inline_media_file_names(
            html, article_id=2, author_id=1
        )

        self.assertEqual(result, set())

    @override_settings(MEDIA_URL="/media/")
    def test_ignores_invalid_and_unsafe_sources(self):
        html = (
            '<img src="data:image/png;base64,abc">'
            '<img src="blob:http://example.test/id">'
            '<img src="javascript:alert(1)">'
            '<img src="/media/articles/uploads/1/2/../evil.jpeg">'
            "<img>"
        )

        result = extract_article_inline_media_file_names(
            html, article_id=2, author_id=1
        )

        self.assertEqual(result, set())

    @override_settings(
        MEDIA_URL="/media/",
        MEDIA_ALLOWED_ROOT_URLS=["https://cdn.test/media/"],
    )
    def test_ignores_absolute_url_from_unallowed_host(self):
        html = '<img src="https://evil.test/media/articles/uploads/1/2/a.jpeg">'

        result = extract_article_inline_media_file_names(
            html, article_id=2, author_id=1
        )

        self.assertEqual(result, set())


class TestDeleteArticleInlineMediaFiles(SimpleTestCase):
    def setUp(self):
        self.article_id = 123
        self.author_id = 1
        self.article_dir = ARTICLE_MEDIA_UPLOAD_DIR_TEMPLATE.format(
            author_id=self.author_id, article_id=self.article_id
        )

    @override_settings(
        STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}}
    )
    def test_local_fs_storage(self):
        self.assertIsInstance(default_storage, FileSystemStorage)

        with patch(
            "articles.services.media._delete_local_filesystem_media"
        ) as mock_delete:
            delete_article_inline_media_files(self.article_id, self.author_id)

        mock_delete.assert_called_once_with(
            self.article_dir, self.article_id, default_storage
        )

    @override_settings(
        STORAGES={"default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}}
    )
    def test_s3_storage(self):
        with patch("articles.services.media._delete_s3_media") as mock_delete:
            delete_article_inline_media_files(self.article_id, self.author_id)

        mock_delete.assert_called_once_with(
            self.article_dir, self.article_id, default_storage
        )

    @override_settings(
        STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}}
    )
    def test_unsupported_storage(self):
        with (
            patch(
                "articles.services.media._delete_local_filesystem_media"
            ) as mock_delete_local,
            patch("articles.services.media._delete_s3_media") as mock_delete_s3,
            self.assertRaises(ImproperlyConfigured) as context,
        ):
            delete_article_inline_media_files(self.article_id, self.author_id)

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
            Bucket="test-bucket", Delete={"Objects": expected_keys}
        )
        mock_logger.info.assert_called_once_with(
            "Successfully deleted media (batch %s) for article %s.", 1, self.article_id
        )

    @patch("articles.services.media.logger")
    def test_multiple_batches(self, mock_logger):
        file_names = [f"img_{i}.jpg" for i in range(MAX_S3_DELETE_BATCH_SIZE + 10)]
        self.storage.listdir.return_value = ([], file_names)

        _delete_s3_media(self.article_dir, self.article_id, self.storage)

        call_1_keys = [
            {"Key": f"{self.posix_dir}/img_{i}.jpg"}
            for i in range(MAX_S3_DELETE_BATCH_SIZE)
        ]
        call_2_keys = [
            {"Key": f"{self.posix_dir}/img_{i}.jpg"}
            for i in range(
                MAX_S3_DELETE_BATCH_SIZE,
                MAX_S3_DELETE_BATCH_SIZE + 10,
            )
        ]

        self.assertEqual(self.s3_client.delete_objects.call_count, 2)
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
                self.article_dir,
                self.article_id,
                storage=FileSystemStorage(),
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
        self.storage.listdir.return_value = ([], ["file1", "file2"])
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

        self.override_media_root = override_settings(MEDIA_ROOT=self.temp_media_root)
        self.override_media_root.enable()
        self.addCleanup(self.override_media_root.disable)

        self.storage = FileSystemStorage(location=self.temp_media_root)

        self.author_id = 42
        self.article_id = 101
        self.author_path = os.path.join(
            self.temp_media_root, "articles", "uploads", str(self.author_id)
        )
        self.article_media_dir = f"articles/uploads/{self.author_id}/{self.article_id}"
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
                self.article_media_dir,
                self.article_id,
                storage=S3Boto3Storage(),
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

        file_path = os.path.join(article_path, "file1.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("content")

        self.assertTrue(os.path.exists(file_path))

        _delete_local_filesystem_media(self.article_media_dir, self.article_id, storage)

        self.assertTrue(os.path.exists(file_path))
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

        mock_rmtree.assert_called_once_with(self.article_path)
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
                self.article_media_dir,
                self.article_id,
                self.storage,
            )

        self.assertEqual(str(context.exception), "OS error")
        mock_rmtree.assert_called_once_with(self.article_path)
        mock_delete.assert_not_called()
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
            "Successfully batch-deleted local files for article %s.", self.article_id
        )


class TestDeleteAuthorMediaDir(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(
            lambda path: shutil.rmtree(path) if os.path.exists(path) else None, self.dir
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
        file_path = os.path.join(self.dir, "file1.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("content")

        self.assertTrue(os.path.exists(file_path))

        _delete_author_media_dir(self.dir)

        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        self.assertTrue(os.path.exists(file_path))

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
