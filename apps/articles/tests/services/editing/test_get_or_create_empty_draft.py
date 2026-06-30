from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from articles.constants import DEFAULT_DRAFT_ARTICLE_TITLE
from articles.models import Article, ArticleStatus
from articles.services.editing import (
    MAX_SLUG_RETRY_ATTEMPTS,
    get_or_create_empty_draft,
)
from users.models import User


class TestGetOrCreateEmptyDraft(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )

    def test_reuses_existing_empty_draft(self):
        existing = get_or_create_empty_draft(author=self.author)
        result = get_or_create_empty_draft(author=self.author)

        self.assertEqual(result, existing)
        self.assertEqual(Article.objects.count(), 1)

    def test_creates_new_draft_when_existing_draft_is_not_empty(self):
        Article.objects.create(
            author=self.author,
            title=DEFAULT_DRAFT_ARTICLE_TITLE,
            slug="existing-draft",
            preview_text="changed",
            content="",
            content_text="",
            status=ArticleStatus.DRAFT,
        )

        article = get_or_create_empty_draft(author=self.author)

        self.assertNotEqual(article.slug, "existing-draft")
        self.assertEqual(Article.objects.count(), 2)

    def test_creates_expected_article(self):
        article = get_or_create_empty_draft(author=self.author)

        self.assertIsNotNone(article.pk)
        self.assertEqual(article.author, self.author)
        self.assertEqual(article.title, DEFAULT_DRAFT_ARTICLE_TITLE)
        self.assertEqual(article.preview_text, "")
        self.assertEqual(article.content, "")
        self.assertEqual(article.status, ArticleStatus.DRAFT)

        self.assertTrue(article.slug)
        self.assertEqual(Article.objects.count(), 1)

    def test_retries_with_suffix_on_slug_collision(self):
        base_title = DEFAULT_DRAFT_ARTICLE_TITLE

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
            "articles.services.editing._build_article_slug_candidate",
            side_effect=["untitled-article", "untitled-article-abc12345"],
        ) as mocked_builder:
            article = get_or_create_empty_draft(author=self.author)

        self.assertEqual(article.slug, "untitled-article-abc12345")
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertEqual(article.author, self.author)
        self.assertEqual(mocked_builder.call_count, 2)
        self.assertEqual(Article.objects.count(), 2)

    @patch(
        "articles.services.editing._build_article_slug_candidate",
        side_effect=["same-slug"] * MAX_SLUG_RETRY_ATTEMPTS,
    )
    def test_raises_after_max_slug_retry_attempts(self, mocked_build_slug):
        Article.objects.create(
            title="Existing",
            slug="same-slug",
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.DRAFT,
        )

        with self.assertRaises(IntegrityError):
            get_or_create_empty_draft(author=self.author)

        self.assertEqual(mocked_build_slug.call_count, MAX_SLUG_RETRY_ATTEMPTS)
        self.assertEqual(Article.objects.filter(slug="same-slug").count(), 1)
