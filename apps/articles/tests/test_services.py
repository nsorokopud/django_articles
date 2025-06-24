import os
import re
from unittest.mock import Mock, call, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.db.utils import IntegrityError
from django.test import TestCase

from articles.models import Article, ArticleCategory, ArticleComment
from articles.services import (
    _generate_unique_article_slug,
    bulk_increment_article_view_counts,
    create_article,
    delete_media_files_attached_to_article,
    increment_article_views_counter,
    save_media_file_attached_to_article,
    toggle_article_like,
    toggle_comment_like,
)
from users.models import User


class TestServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test_user@test.com"
        )
        self.test_category = ArticleCategory.objects.create(
            title="test_cat", slug="test_cat"
        )

    def test__generate_unique_article_slug(self):
        self.assertEqual(_generate_unique_article_slug("abc"), "abc")

        Article.objects.create(
            title="abc",
            slug="abc",
            author=self.test_user,
            preview_text="1",
            content="1",
        )

        self.assertEqual(_generate_unique_article_slug("abc"), "abc")
        self.assertEqual(_generate_unique_article_slug("abc "), "abc-1")

        Article.objects.create(
            title="abc-",
            slug="abc-1",
            author=self.test_user,
            preview_text="1",
            content="1",
        )
        self.assertEqual(_generate_unique_article_slug("abc"), "abc")
        self.assertEqual(_generate_unique_article_slug("abc-"), "abc-1")
        self.assertEqual(_generate_unique_article_slug("abc -"), "abc-2")

    def test_create_article(self):
        a1 = create_article(
            title="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        # articles are sorted by '-created_at' by default, so the last one created will
        # be the first one in queryset
        last_article = Article.objects.first()

        self.assertEqual(last_article.pk, a1.pk)
        self.assertEqual(last_article.slug, "a1")
        self.assertEqual(last_article.author.username, "test_user")

        expected_tags = ["tag1", "tag2"]
        actual_tags = [tag.name for tag in last_article.tags.all()]
        self.assertCountEqual(actual_tags, expected_tags)

    def test_create_article_with_same_title(self):
        a1 = create_article(
            title="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        a2 = create_article(
            title="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )

        self.assertEqual(a1.slug, "a1")
        self.assertEqual(a2.slug, "a2")

        with self.assertRaises(IntegrityError):
            a3 = create_article(
                title="a1",
                category=self.test_category,
                author=self.test_user,
                preview_text="text1",
                content="content1",
                tags=["tag1", "tag2"],
            )

        self.assertEqual(Article.objects.count(), 2)
        last_article = Article.objects.first()
        self.assertEqual(last_article, a2)

    def test_create_article_tags_creation(self):
        a1 = create_article(
            title="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        a1_actual_tags = [t.name for t in a1.tags.all()]
        self.assertCountEqual(a1_actual_tags, ["tag1", "tag2"])

        a2 = create_article(
            title="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )

        a2_actual_tags = [t.name for t in a2.tags.all()]
        self.assertCountEqual(a2_actual_tags, [])

    def test_toggle_article_like(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

        user = User(username="user1", email="test@test.com")
        user.set_password("12345")
        user.save()

        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEqual(likes_count, 0)

        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_article_like(a.slug, user.id)
        self.assertEqual(likes_count, 2)
        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_article_like(a.slug, user.id)
        self.assertEqual(likes_count, 0)

    def test_toggle_comment_like(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        comment = ArticleComment.objects.create(
            article=a, author=self.test_user, text="text"
        )

        user = User(username="user1", email="test@test.com")
        user.set_password("12345")
        user.save()

        likes_count = toggle_comment_like(comment.id, self.test_user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_comment_like(comment.id, self.test_user.id)
        self.assertEqual(likes_count, 0)

        likes_count = toggle_comment_like(comment.id, self.test_user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_comment_like(comment.id, user.id)
        self.assertEqual(likes_count, 2)
        likes_count = toggle_comment_like(comment.id, self.test_user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_comment_like(comment.id, user.id)
        self.assertEqual(likes_count, 0)

    def test_increment_article_views_count(self):
        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        self.assertEqual(a1.views_count, 0)
        new_views_count = increment_article_views_counter(a1)
        self.assertEqual(new_views_count, 1)
        self.assertEqual(a1.views_count, 1)
        new_views_count = increment_article_views_counter(a1)
        self.assertEqual(new_views_count, 2)
        self.assertEqual(a1.views_count, 2)

    def test_save_media_file_attached_to_article(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )

        file_name = "file.jpg"
        file_path = (
            f"articles/uploads/{self.test_user.username}/{a.id}/file_xyz-xyz.jpg"
        )
        file = SimpleUploadedFile(file_name, b"file_content", content_type="image/jpg")

        with self.assertRaises(Article.DoesNotExist):
            save_media_file_attached_to_article(file, -1)

        with (
            patch("articles.services.uuid4", return_value="xyz-xyz") as uuid_mock,
            patch(
                "articles.services.default_storage.save", side_effect=[file_name]
            ) as save_mock,
        ):
            res = save_media_file_attached_to_article(file, a.id)
            uuid_mock.assert_called_once()
            save_mock.assert_called_once_with(file_path, file)
            self.assertEqual(res[0], file_path)
            self.assertEqual(res[1], a.get_absolute_url())

    def test_delete_media_files_attached_to_article(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )
        directory = f"articles/uploads/{self.test_user.username}/{a.id}"

        with (
            patch("articles.services.default_storage.exists", return_value=True),
            patch(
                "articles.services.default_storage.listdir",
                return_value=[[directory], ["file1", "file2"]],
            ),
            patch("articles.services.default_storage.delete") as delete_mock,
        ):

            delete_media_files_attached_to_article(a)
            delete_mock.assert_has_calls(
                [
                    call(os.path.join(directory, "file1")),
                    call(os.path.join(directory, "file2")),
                    call(directory),
                ],
                any_order=False,
            )


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
        with patch("articles.services.logger.warning") as mock_warn:
            bulk_increment_article_view_counts({})
            mock_warn.assert_called_once_with("No deltas to process for bulk update.")

    def test_db_error(self):
        self.patch_cursor()
        self.mocked_cursor.execute.side_effect = DatabaseError("DB failed")

        with patch("articles.services.logger.exception") as mock_exc:
            bulk_increment_article_view_counts({1: 5})
            mock_exc.assert_called_once()
