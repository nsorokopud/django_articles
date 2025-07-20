import re
from unittest.mock import Mock, patch

from django.db import DatabaseError
from django.test import TestCase

from articles.models import Article
from articles.services import bulk_increment_article_view_counts
from users.models import User


class TestBulkIncrementArticleViewCounts(TestCase):
    def patch_cursor(self):
        self.cursor_patcher = patch("articles.services.connection.cursor")
        self.mock_cursor_context = self.cursor_patcher.start()
        self.mocked_cursor = Mock()
        self.mock_cursor_context.return_value.__enter__.return_value = (
            self.mocked_cursor
        )
        self.addCleanup(self.cursor_patcher.stop)

    def test_correct_sql(self):
        self.patch_cursor()
        view_deltas = {1: 10, 2: 5}

        bulk_increment_article_view_counts(view_deltas)

        case_statements = []
        case_params = []
        where_placeholders = []
        where_params = []

        for article_id, view_delta in sorted(view_deltas.items()):
            case_statements.append("WHEN id = %s THEN views_count + %s")
            case_params.extend([article_id, view_delta])
            where_placeholders.append("%s")
            where_params.append(article_id)

        case_sql = "CASE " + " ".join(case_statements) + " END"
        where_clause = f"id IN ({', '.join(where_placeholders)})"

        expected_sql = f"""
            UPDATE articles_article
            SET views_count = {case_sql}
            WHERE {where_clause}
        """
        expected_params = [1, 10, 2, 5, 1, 2]

        actual_sql = self.mocked_cursor.execute.call_args_list[1][0][0]
        actual_params = self.mocked_cursor.execute.call_args_list[1][0][1]
        self.assertEqual(
            re.sub(r"\s+", " ", actual_sql.strip()),
            re.sub(r"\s+", " ", expected_sql.strip()),
        )
        self.assertEqual(actual_params, expected_params)

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

    def test_db_error(self):
        self.patch_cursor()
        self.mocked_cursor.execute.side_effect = DatabaseError("DB failed")

        with patch("articles.services.articles.logger.exception") as mock_exc:
            bulk_increment_article_view_counts({1: 5})
            mock_exc.assert_called_once()
