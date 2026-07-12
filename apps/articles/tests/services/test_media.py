from datetime import timedelta
from unittest.mock import call, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from articles.models import Article, ArticleMedia
from articles.services.media import (
    ARTICLE_MEDIA_UNUSED_GRACE_PERIOD,
    cleanup_unused_article_inline_media,
    extract_article_inline_media_file_names,
    save_article_inline_media_file,
    sync_article_inline_media_references,
)
from core.exceptions import MediaSaveError
from users.models import User


class TestSaveArticleInlineMediaFile(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", email="tester@test.com")
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

        self.assertEqual(len(name), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in name))

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
            "Failed to upload media for article %s", self.article.id
        )
        self.assertFalse(ArticleMedia.objects.filter(article=self.article).exists())

    @patch("articles.services.media.logger")
    @patch("articles.models.uuid4")
    @patch("articles.services.media.ArticleMedia.save")
    def test_db_save_failure_deletes_uploaded_file(
        self, mock_media_save, mock_uuid, mock_logger
    ):
        mock_uuid.return_value.hex = "abc123"
        mock_media_save.side_effect = DatabaseError("DB error")
        file = SimpleUploadedFile("file.jpeg", b"test", content_type="image/jpeg")

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            with self.assertRaises(MediaSaveError) as context:
                save_article_inline_media_file(file, self.article)

        self.assertIsInstance(context.exception.__cause__, DatabaseError)
        mock_delete.assert_called_once()
        self.assertFalse(ArticleMedia.objects.filter(article=self.article).exists())

        deleted_path = mock_delete.call_args.args[0]
        self.assertTrue(
            deleted_path.startswith(
                f"articles/uploads/{self.user.id}/{self.article.id}/abc123"
            )
        )
        self.assertTrue(deleted_path.endswith(".jpeg"))
        mock_logger.exception.assert_called_once_with(
            "Failed to create media record for article %s", self.article.id
        )


class TestSyncArticleInlineMediaReferences(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", email="tester@test.com")
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
        self.user = User.objects.create_user(username="tester", email="tester@test.com")
        self.article = Article.objects.create(
            title="a1", slug="a1", content="content", author=self.user
        )

    def test_skips_media_if_no_longer_unreferenced(self):
        old_time = (
            timezone.now() - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD - timedelta(seconds=1)
        )
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/old.jpeg",
            unreferenced_at=old_time,
        )

        ArticleMedia.objects.filter(id=media.id).update(unreferenced_at=None)

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 0)
        mock_delete.assert_not_called()
        self.assertTrue(ArticleMedia.objects.filter(id=media.id).exists())

    def test_deletes_old_unreferenced_media(self):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/old.jpeg",
            unreferenced_at=timezone.now()
            - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD
            - timedelta(seconds=1),
        )

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 1)
        mock_delete.assert_called_once_with(media.file.name)
        self.assertFalse(ArticleMedia.objects.filter(id=media.id).exists())

    def test_keeps_recent_unreferenced_media(self):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/recent.jpeg",
            unreferenced_at=timezone.now(),
        )

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 0)
        mock_delete.assert_not_called()
        self.assertTrue(ArticleMedia.objects.filter(id=media.id).exists())

    def test_keeps_referenced_media(self):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/used.jpeg",
            unreferenced_at=None,
        )

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 0)
        mock_delete.assert_not_called()
        self.assertTrue(ArticleMedia.objects.filter(id=media.id).exists())

    def test_marks_orphaned_referenced_media_as_unreferenced(self):
        media = ArticleMedia.objects.create(
            article=None,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/orphan.jpeg",
            unreferenced_at=None,
        )

        before = timezone.now()
        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=500)
        after = timezone.now()

        self.assertEqual(deleted_count, 0)
        mock_delete.assert_not_called()

        media.refresh_from_db()
        self.assertGreaterEqual(media.unreferenced_at, before)
        self.assertLessEqual(media.unreferenced_at, after)

    def test_deletes_old_orphaned_unreferenced_media(self):
        media = ArticleMedia.objects.create(
            article=None,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/orphan.jpeg",
            unreferenced_at=timezone.now()
            - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD
            - timedelta(seconds=1),
        )

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 1)
        mock_delete.assert_called_once_with(media.file.name)
        self.assertFalse(ArticleMedia.objects.filter(id=media.id).exists())

    def test_deletes_multiple_old_unreferenced_media(self):
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

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=500)

        self.assertEqual(deleted_count, 2)
        mock_delete.assert_has_calls([call(media_1.file.name), call(media_2.file.name)])
        self.assertFalse(ArticleMedia.objects.filter(id=media_1.id).exists())
        self.assertFalse(ArticleMedia.objects.filter(id=media_2.id).exists())

    def test_keeps_row_when_storage_delete_fails(self):
        media = ArticleMedia.objects.create(
            article=self.article,
            file=f"articles/uploads/{self.user.id}/{self.article.id}/old.jpeg",
            unreferenced_at=timezone.now()
            - ARTICLE_MEDIA_UNUSED_GRACE_PERIOD
            - timedelta(seconds=1),
        )

        with patch.object(
            ArticleMedia._meta.get_field("file").storage,
            "delete",
            side_effect=OSError("Storage unavailable"),
        ):
            with self.assertRaises(OSError):
                cleanup_unused_article_inline_media(batch_size=500)

        self.assertTrue(ArticleMedia.objects.filter(id=media.id).exists())

    def test_respects_batch_size(self):
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

        with patch.object(
            ArticleMedia._meta.get_field("file").storage, "delete"
        ) as mock_delete:
            deleted_count = cleanup_unused_article_inline_media(batch_size=1)

        self.assertEqual(deleted_count, 1)
        mock_delete.assert_called_once_with(media_1.file.name)
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
