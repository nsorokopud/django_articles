from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchQuery
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from config.settings import CACHES


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

    @override_settings(CACHES=CACHES)
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
            publish_sequence=1,
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
            publish_sequence=1,
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

    def test_published_requires_published_at_and_publish_sequence(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="Published",
                    slug="bad-published",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    status=ArticleStatus.PUBLISHED,
                    published_at=None,
                    publish_sequence=None,
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
                    status=ArticleStatus.DRAFT,
                    published_at=timezone.now(),
                    publish_sequence=1,
                )

    def test_published_at_and_publish_sequence_must_be_set_together(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="Draft",
                    slug="no-sequence",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    status=ArticleStatus.DRAFT,
                    published_at=timezone.now(),
                    publish_sequence=None,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="Draft",
                    slug="no-published-at",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    status=ArticleStatus.DRAFT,
                    published_at=None,
                    publish_sequence=1,
                )

    def test_publish_sequence_must_be_unique_when_not_null(self):
        Article.objects.create(
            title="Article 1",
            slug="article-1",
            author=self.user,
            preview_text="Preview",
            content="Content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=100,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="Article 2",
                    slug="article-2",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    status=ArticleStatus.PUBLISHED,
                    published_at=timezone.now(),
                    publish_sequence=100,
                )

    def test_non_draft_requires_title_preview_and_content(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    title="",
                    slug="bad-pending",
                    author=self.user,
                    preview_text="Preview",
                    content="Content",
                    status=ArticleStatus.PENDING_REVIEW,
                )

    def test_draft_allows_blank_core_fields(self):
        article = Article.objects.create(
            title="",
            slug="blank-draft",
            author=self.user,
            preview_text="",
            content="",
            status=ArticleStatus.DRAFT,
        )

        self.assertEqual(article.status, ArticleStatus.DRAFT)
