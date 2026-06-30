from unittest.mock import patch

from django.test import SimpleTestCase

from articles.models import ARTICLE_SLUG_MAX_LENGTH
from articles.services.editing import (
    ARTICLE_SLUG_SUFFIX_LENGTH,
    _build_article_slug_candidate,
)


class TestBuildArticleSlugCandidate(SimpleTestCase):
    def test_truncates_unsuffixed_slug_to_max_length(self):
        title = "a" * (ARTICLE_SLUG_MAX_LENGTH + 50)

        slug = _build_article_slug_candidate(title, use_suffix=False)

        self.assertEqual(len(slug), ARTICLE_SLUG_MAX_LENGTH)
        self.assertEqual(slug, "a" * ARTICLE_SLUG_MAX_LENGTH)

    @patch("articles.services.editing.generate")
    def test_keeps_suffixed_slug_within_max_length(self, mock_generate):
        mock_generate.return_value = "abc123xy"
        title = "a" * (ARTICLE_SLUG_MAX_LENGTH + 50)

        slug = _build_article_slug_candidate(title, use_suffix=True)

        expected_base_length = ARTICLE_SLUG_MAX_LENGTH - ARTICLE_SLUG_SUFFIX_LENGTH - 1

        self.assertEqual(len(slug), ARTICLE_SLUG_MAX_LENGTH)
        self.assertEqual(slug, f"{'a' * expected_base_length}-abc123xy")

    @patch("articles.services.editing.generate")
    def test_removes_trailing_hyphen_before_suffix(self, mock_generate):
        mock_generate.return_value = "abc123xy"

        max_base_length = ARTICLE_SLUG_MAX_LENGTH - ARTICLE_SLUG_SUFFIX_LENGTH - 1
        title = f"{'a' * (max_base_length - 1)} bbb"

        slug = _build_article_slug_candidate(title, use_suffix=True)

        self.assertLessEqual(len(slug), ARTICLE_SLUG_MAX_LENGTH)
        self.assertNotIn("--abc123xy", slug)
        self.assertTrue(slug.endswith("-abc123xy"))

    def test_falls_back_to_article_for_blank_title(self):
        slug = _build_article_slug_candidate(" --- ", use_suffix=False)

        self.assertEqual(slug, "article")

    @patch("articles.services.editing.generate")
    def test_falls_back_to_article_with_suffix(self, mock_generate):
        mock_generate.return_value = "abc123xy"

        slug = _build_article_slug_candidate(" --- ", use_suffix=True)

        self.assertEqual(slug, "article-abc123xy")
