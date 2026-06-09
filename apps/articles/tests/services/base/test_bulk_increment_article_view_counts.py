from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase

from articles.models import Article
from articles.services.articles import bulk_increment_article_view_counts
from users.models import User


class TestBulkIncrementArticleViewCounts(TestCase):
    def test_increments_view_counts(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        a1 = Article(
            title="a1",
            slug="a1",
            author=user,
            preview_text="1",
            content="1",
            views_count=0,
        )
        a2 = Article(
            title="a2",
            slug="a2",
            author=user,
            preview_text="2",
            content="2",
            views_count=100,
        )
        a3 = Article(
            title="a3",
            slug="a3",
            author=user,
            preview_text="3",
            content="3",
            views_count=50,
        )
        Article.objects.bulk_create([a1, a2, a3])

        view_deltas = {a1.id: 10, a2.id: 5}
        bulk_increment_article_view_counts(view_deltas)

        a1.refresh_from_db()
        a2.refresh_from_db()
        a3.refresh_from_db()

        self.assertEqual(a1.views_count, 10)
        self.assertEqual(a2.views_count, 105)
        self.assertEqual(a3.views_count, 50)

    def test_empty_input(self):
        with patch("articles.services.articles.logger.warning") as mock_warn:
            bulk_increment_article_view_counts({})
            mock_warn.assert_called_once_with("No deltas to process for bulk update.")

    def test_db_error_is_logged_and_reraised(self):
        with patch("articles.services.articles.Article.objects.filter") as mock_filter:
            mock_filter.return_value.update.side_effect = DatabaseError("DB failed")

            with patch("articles.services.articles.logger.exception") as mock_exc:
                with self.assertRaises(DatabaseError):
                    bulk_increment_article_view_counts({1: 5})

        mock_exc.assert_called_once_with("Failed to bulk update view counts.")
