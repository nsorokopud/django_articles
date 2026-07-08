from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchQuery
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from articles.models import (
    ARTICLE_SLUG_UNIQUE_CONSTRAINT_NAME,
    Article,
    ArticleCategory,
    ArticleMedia,
    ArticleStatus,
    article_inline_media_upload_path,
    article_preview_image_upload_path,
)
from tests.cache_settings import override_settings_with_redis_cache


User = get_user_model()


class TestArticleModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")

        self.unpublished_article = Article.objects.create(
            title="draft article",
            author=self.user,
            preview_text="draft preview",
            content="draft content",
        )

    def test_preview_image_has_uploaded_image_validator(self):
        field = Article._meta.get_field("preview_image")

        validator_names = {validator.__name__ for validator in field.validators}

        self.assertIn("validate_uploaded_image", validator_names)

    @override_settings_with_redis_cache()
    def test_views_property(self):
        self.assertEqual(self.unpublished_article.views, 0)

        self.unpublished_article.views_count = 10
        self.unpublished_article.save(update_fields=["views_count"])

        with patch(
            "articles.cache.view_counts.get_cached_article_views"
        ) as mock_get_cached:
            mock_get_cached.return_value = 5
            self.assertEqual(self.unpublished_article.views, 15)
            mock_get_cached.assert_called_once_with(self.unpublished_article.id)


class TestArticleSearchVectorColumn(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

    def test_search_vector_is_generated_in_db(self):
        article = Article.objects.create(
            title="python tutorial",
            slug="python-tutorial",
            category=self.category,
            author=self.user,
            preview_text="learn django fast",
            content="<p>Hello <strong>world</strong></p>",
            content_text="Hello world",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    content_text,
                    search_vector IS NOT NULL,
                    search_vector::text
                FROM articles_article
                WHERE id = %s
                """,
                [article.id],
            )
            content_text, has_search_vector, search_vector_text = cursor.fetchone()

        self.assertEqual(content_text, "Hello world")
        self.assertTrue(has_search_vector)
        self.assertIn("python", search_vector_text)
        self.assertIn("django", search_vector_text)
        self.assertIn("hello", search_vector_text)
        self.assertIn("world", search_vector_text)

    def test_search_vector_updates_when_fields_change(self):
        article = Article.objects.create(
            title="old title",
            slug="old-title",
            category=self.category,
            author=self.user,
            preview_text="old preview",
            content="old content",
            content_text="old content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
        )

        article.title = "quantum django"
        article.preview_text = "postgres search"
        article.content_text = "generated vector update"
        article.save(update_fields=["title", "preview_text", "content_text"])

        self.assertTrue(
            Article.objects.filter(
                pk=article.pk,
                search_vector=SearchQuery(
                    "postgres", config="english", search_type="websearch"
                ),
            ).exists()
        )

        self.assertTrue(
            Article.objects.filter(
                pk=article.pk,
                search_vector=SearchQuery(
                    "quantum", config="english", search_type="websearch"
                ),
            ).exists()
        )

        self.assertTrue(
            Article.objects.filter(
                pk=article.pk,
                search_vector=SearchQuery(
                    "vector update", config="english", search_type="websearch"
                ),
            ).exists()
        )


class TestArticleModelConstraints(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_slug_must_be_unique(self):
        Article.objects.create(
            title="Article 1",
            slug="same-slug",
            author=self.user,
            preview_text="Preview",
            content="Content",
            content_text="Content",
        )

        with self.assertRaises(IntegrityError) as ctx:
            with transaction.atomic():
                Article.objects.create(
                    title="Article 2",
                    slug="same-slug",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    content_text="Content",
                )

        diagnostics = getattr(ctx.exception.__cause__, "diag", None)
        self.assertEqual(
            getattr(diagnostics, "constraint_name", None),
            ARTICLE_SLUG_UNIQUE_CONSTRAINT_NAME,
        )

    def test_published_requires_published_at(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="Published",
                    slug="bad-published",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    content_text="Content",
                    status=ArticleStatus.PUBLISHED,
                    published_at=None,
                )

    def test_draft_cannot_have_publication_fields(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="Draft",
                    slug="bad-draft",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    content_text="Content",
                    status=ArticleStatus.DRAFT,
                    published_at=timezone.now(),
                )

    def test_non_draft_requires_non_whitespace_title_preview_and_content_text(self):
        cases = [
            {
                "title": "   ",
                "preview_text": "Preview",
                "content": "Content",
                "content_text": "Content",
            },
            {
                "title": "Title",
                "preview_text": "   ",
                "content": "Content",
                "content_text": "Content",
            },
            {
                "title": "Title",
                "preview_text": "Preview",
                "content": "Content",
                "content_text": "   ",
            },
        ]

        for index, data in enumerate(cases):
            with self.subTest(data=data):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Article.objects.create(
                            slug=f"bad-whitespace-{index}",
                            author=self.user,
                            status=ArticleStatus.PENDING_REVIEW,
                            **data,
                        )

    def test_non_draft_requires_non_blank_core_fields(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="",
                    slug="bad-pending",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    content_text="Content",
                    status=ArticleStatus.PENDING_REVIEW,
                )

    def test_non_draft_allows_raw_html_when_content_text_has_text(self):
        article = Article.objects.create(
            title="Title",
            slug="html-content",
            author=self.user,
            preview_text="Preview",
            content="<p><strong>Content</strong></p>",
            content_text="Content",
            status=ArticleStatus.PENDING_REVIEW,
        )

        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)

    def test_draft_allows_blank_core_fields(self):
        article = Article.objects.create(
            title="",
            slug="blank-draft",
            author=self.user,
            preview_text="",
            content="",
            content_text="",
            status=ArticleStatus.DRAFT,
        )

        self.assertEqual(article.status, ArticleStatus.DRAFT)


class TestArticlePreviewImageUploadPath(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.article = Article.objects.create(
            author=self.author,
            title="a",
            slug="a",
            preview_text="preview",
            content="content",
            content_text="content",
        )

    def test_requires_author_id(self):
        article = Article(title="Test")

        with self.assertRaises(ValueError) as context:
            article.preview_image.field.generate_filename(article, "preview.jpg")

        self.assertIn("author_id is required", str(context.exception))

    @patch("articles.models.uuid4")
    def test_uses_author_id(self, mock_uuid4):
        mock_uuid4.return_value.hex = "abc123"

        path = article_preview_image_upload_path(self.article, "Preview Image.PNG")

        self.assertEqual(path, f"articles/preview_images/{self.author.id}/abc123.png")

    @patch("articles.models.uuid4")
    def test_uses_uuid_only_filename_with_sanitized_extension(self, mock_uuid4):
        mock_uuid4.return_value.hex = "abc123"

        path = article_preview_image_upload_path(
            self.article, "../../bad preview image!!.JPG"
        )

        self.assertEqual(
            path,
            f"articles/preview_images/{self.author.id}/abc123.jpg",
        )

    @patch("articles.models.uuid4")
    def test_uses_uuid_only_name_when_original_base_is_empty(
        self,
        mock_uuid4,
    ):
        mock_uuid4.return_value.hex = "abc123"

        path = article_preview_image_upload_path(self.article, "...---.webp")

        self.assertEqual(path, f"articles/preview_images/{self.author.id}/abc123.webp")

    @patch("articles.models.uuid4")
    def test_handles_missing_extension(
        self,
        mock_uuid4,
    ):
        mock_uuid4.return_value.hex = "abc123"

        path = article_preview_image_upload_path(self.article, "preview")

        self.assertEqual(path, f"articles/preview_images/{self.author.id}/abc123")

    @patch("articles.models.uuid4")
    def test_uses_posix_separators(self, mock_uuid4):
        mock_uuid4.return_value.hex = "abc123"

        path = article_preview_image_upload_path(self.article, "preview.webp")

        expected = f"articles/preview_images/{self.author.id}/abc123.webp"

        self.assertEqual(path, expected)
        self.assertNotIn("\\", path)


class TestArticleMediaModel(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.article = Article.objects.create(author=self.author, title="a", slug="a")

    @patch("articles.models.uuid4")
    def test_article_inline_media_upload_path_uses_article_author_and_article_id(
        self, mock_uuid4
    ):
        mock_uuid4.return_value.hex = "abc123"

        media = ArticleMedia(article=self.article)

        path = article_inline_media_upload_path(media, "My Image.PNG")

        self.assertEqual(
            path,
            f"articles/uploads/{self.author.id}/{self.article.id}/abc123.png",
        )

    @patch("articles.models.uuid4")
    def test_article_inline_media_upload_path_uses_uuid_only_filename(self, mock_uuid4):
        mock_uuid4.return_value.hex = "abc123"

        media = ArticleMedia(article=self.article)

        path = article_inline_media_upload_path(media, "../../bad file name!!.JPG")

        self.assertEqual(
            path,
            f"articles/uploads/{self.author.id}/{self.article.id}/abc123.jpg",
        )

    @patch("articles.models.uuid4")
    def test_article_inline_media_upload_path_uses_posix_separators(self, mock_uuid4):
        mock_uuid4.return_value.hex = "abc123"

        media = ArticleMedia(article=self.article)
        path = article_inline_media_upload_path(media, "image.webp")

        expected = f"articles/uploads/{self.author.id}/{self.article.id}/abc123.webp"

        self.assertEqual(path, expected)
        self.assertNotIn("\\", path)  # ensure no Windows separators

    @patch("articles.models.uuid4")
    def test_article_inline_media_upload_path_handles_missing_extension(
        self, mock_uuid4
    ):
        mock_uuid4.return_value.hex = "abc123"

        media = ArticleMedia(article=self.article)

        path = article_inline_media_upload_path(media, "image")

        self.assertEqual(
            path,
            f"articles/uploads/{self.author.id}/{self.article.id}/abc123",
        )

    def test_article_media_defaults_to_referenced_state_unknown(self):
        media = ArticleMedia.objects.create(
            article=self.article, file="articles/uploads/1/1/example.png"
        )

        self.assertIsNotNone(media.created_at)
        self.assertIsNone(media.unreferenced_at)

    def test_article_media_str(self):
        media = ArticleMedia.objects.create(
            article=self.article, file="articles/uploads/1/1/example.png"
        )

        self.assertEqual(
            str(media), f"Media for {self.article} - articles/uploads/1/1/example.png"
        )

    def test_article_media_is_deleted_when_article_is_deleted(self):
        media = ArticleMedia.objects.create(
            article=self.article, file="articles/uploads/1/1/example.png"
        )

        self.article.delete()

        self.assertFalse(ArticleMedia.objects.filter(id=media.id).exists())
