from unittest.mock import patch

from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase, override_settings

from articles.models import Article, ArticleStatus
from articles.services.articles import MAX_SLUG_RETRY_ATTEMPTS, create_empty_draft
from users.models import User


class TestCreateEmptyDraft(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )

    def test_creates_expected_article(self):
        article = create_empty_draft(author=self.author)

        self.assertIsNotNone(article.pk)
        self.assertEqual(article.author, self.author)
        self.assertEqual(article.title, settings.DEFAULT_DRAFT_ARTICLE_TITLE)
        self.assertEqual(article.preview_text, "")
        self.assertEqual(article.content, "")
        self.assertEqual(article.status, ArticleStatus.DRAFT)

        self.assertTrue(article.slug)
        self.assertEqual(Article.objects.count(), 1)

    @override_settings(DEFAULT_DRAFT_ARTICLE_TITLE="Untitled article")
    def test_retries_with_suffix_on_slug_collision(self):
        base_title = settings.DEFAULT_DRAFT_ARTICLE_TITLE

        existing = Article.objects.create(
            author=self.author,
            title=base_title,
            slug="untitled-article",
            preview_text="already exists",
            content="x",
            status=ArticleStatus.DRAFT,
        )

        self.assertIsNotNone(existing.pk)

        with patch(
            "articles.services.articles._build_article_slug_candidate",
            side_effect=["untitled-article", "untitled-article-abc12345"],
        ) as mocked_builder:
            article = create_empty_draft(author=self.author)

        self.assertEqual(article.slug, "untitled-article-abc12345")
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertEqual(article.author, self.author)
        self.assertEqual(mocked_builder.call_count, 2)
        self.assertEqual(Article.objects.count(), 2)

    def test_raises_after_max_slug_retry_attempts(self):
        with (
            patch(
                "articles.services.articles._build_article_slug_candidate",
                side_effect=["same-slug"] * MAX_SLUG_RETRY_ATTEMPTS,
            ),
            patch(
                "articles.models.Article.save",
                side_effect=IntegrityError(
                    "duplicate key value violates unique constraint"
                ),
            ) as mocked_save,
        ):
            with self.assertRaises(IntegrityError):
                create_empty_draft(author=self.author)

        self.assertEqual(mocked_save.call_count, MAX_SLUG_RETRY_ATTEMPTS)
        self.assertEqual(Article.objects.count(), 0)
