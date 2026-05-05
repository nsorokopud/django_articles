# pylint: disable=R0801

from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from articles.services.comments import (
    create_article_comment,
    decrement_article_comments_count,
    get_article_comments_page,
    increment_article_comments_count,
    sync_article_comments_count,
)
from users.models import User


class TestCreateArticleComment(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.commenter = User.objects.create_user(
            username="commenter", email="commenter@test.com"
        )
        self.article = Article.objects.create(
            title="article",
            slug="article",
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )

    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_raises_value_error_when_article_not_published(
        self, mock_create_notification, mock_dispatch
    ):
        self.article.status = ArticleStatus.DRAFT
        self.article.published_at = None
        self.article.publish_sequence = None
        self.article.save(update_fields=["status", "published_at", "publish_sequence"])

        with self.assertRaises(ValueError):
            create_article_comment(article=self.article, user=self.commenter, text="c")

    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_creates_comment_and_dispatches_notification_when_created(
        self,
        mock_create_notification,
        mock_dispatch,
    ):
        notification = type(
            "NotificationStub", (), {"id": 123, "notification_type": "new_comment"}
        )()
        mock_create_notification.return_value = (notification, True)

        comment = create_article_comment(
            article=self.article, user=self.commenter, text="hello world"
        )

        self.assertIsInstance(comment, ArticleComment)
        self.assertEqual(comment.article, self.article)
        self.assertEqual(comment.author, self.commenter)
        self.assertEqual(comment.text, "hello world")

        db_comment = ArticleComment.objects.get(id=comment.id)
        self.assertEqual(db_comment.article, self.article)
        self.assertEqual(db_comment.author, self.commenter)
        self.assertEqual(db_comment.text, "hello world")

        mock_create_notification.assert_called_once_with(
            comment_id=comment.id,
            comment_author_id=self.commenter.id,
            comment_author_username=self.commenter.username,
            article_id=self.article.id,
            article_author_id=self.article.author_id,
            article_slug=self.article.slug,
            article_title=self.article.title,
        )
        mock_dispatch.assert_called_once_with(
            notification_id=123, notification_type="new_comment", is_new_unread=True
        )

    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_creates_comment_and_dispatches_notification_when_unread_state_returned(
        self,
        mock_create_notification,
        mock_dispatch,
    ):
        notification = type(
            "NotificationStub", (), {"id": 456, "notification_type": "new_comment"}
        )()
        mock_create_notification.return_value = (notification, False)

        comment = create_article_comment(
            article=self.article, user=self.commenter, text="another comment"
        )

        self.assertTrue(
            ArticleComment.objects.filter(
                id=comment.id,
                article=self.article,
                author=self.commenter,
                text="another comment",
            ).exists()
        )

        mock_dispatch.assert_called_once_with(
            notification_id=456, notification_type="new_comment", is_new_unread=False
        )

    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_creates_comment_and_does_not_dispatch_when_notification_not_created(
        self,
        mock_create_notification,
        mock_dispatch,
    ):
        mock_create_notification.return_value = None

        comment = create_article_comment(
            article=self.article, user=self.commenter, text="no notification"
        )

        self.assertTrue(
            ArticleComment.objects.filter(
                id=comment.id,
                article=self.article,
                author=self.commenter,
                text="no notification",
            ).exists()
        )

        mock_create_notification.assert_called_once_with(
            comment_id=comment.id,
            comment_author_id=self.commenter.id,
            comment_author_username=self.commenter.username,
            article_id=self.article.id,
            article_author_id=self.article.author_id,
            article_slug=self.article.slug,
            article_title=self.article.title,
        )
        mock_dispatch.assert_not_called()

    @patch("articles.services.comments.logger.exception")
    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_keeps_comment_when_notification_creation_raises_runtime_error(
        self,
        mock_create_notification,
        mock_dispatch,
        mock_log_exception,
    ):
        mock_create_notification.side_effect = RuntimeError("notification failure")

        comment = create_article_comment(
            article=self.article, user=self.commenter, text="should persist"
        )

        self.assertTrue(
            ArticleComment.objects.filter(
                id=comment.id,
                article=self.article,
                author=self.commenter,
                text="should persist",
            ).exists()
        )
        mock_dispatch.assert_not_called()
        mock_log_exception.assert_called_once()

    @patch("articles.services.comments.logger.exception")
    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_keeps_comment_when_notification_creation_raises_integrity_error(
        self,
        mock_create_notification,
        mock_dispatch,
        mock_log_exception,
    ):
        mock_create_notification.side_effect = IntegrityError("db failure")

        comment = create_article_comment(
            article=self.article, user=self.commenter, text="should also persist"
        )

        self.assertTrue(
            ArticleComment.objects.filter(
                id=comment.id,
                article=self.article,
                author=self.commenter,
                text="should also persist",
            ).exists()
        )
        mock_dispatch.assert_not_called()
        mock_log_exception.assert_called_once()


class TestIncrementArticleCommentsCount(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.article = Article.objects.create(
            title="Article", slug="article", author=self.author, comments_count=0
        )

    def test_increments_comments_count_by_one(self):
        increment_article_comments_count(article_id=self.article.id)

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 1)

    def test_multiple_increments_are_accumulative(self):
        increment_article_comments_count(article_id=self.article.id)
        increment_article_comments_count(article_id=self.article.id)
        increment_article_comments_count(article_id=self.article.id)

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 3)

    def test_does_nothing_for_nonexistent_article(self):
        increment_article_comments_count(article_id=999999)

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 0)


class TestDecrementArticleCommentsCount(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.article = Article.objects.create(
            title="Article", slug="article", author=self.author, comments_count=0
        )

    def test_decrements_existing_count(self):
        Article.objects.filter(pk=self.article.pk).update(comments_count=2)

        decrement_article_comments_count(article_id=self.article.id)

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 1)

    def test_count_does_not_go_below_zero(self):
        Article.objects.filter(pk=self.article.pk).update(comments_count=0)

        decrement_article_comments_count(article_id=self.article.id)

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 0)


@patch("articles.services.comments.ARTICLE_COMMENTS_PER_PAGE", 2)
class TestGetArticleCommentsPage(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com"
        )
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.user,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )

        self.comment1 = ArticleComment.objects.create(
            article=self.article, author=self.user, text="comment 1"
        )
        self.comment2 = ArticleComment.objects.create(
            article=self.article, author=self.user, text="comment 2"
        )
        self.comment3 = ArticleComment.objects.create(
            article=self.article, author=self.user, text="comment 3"
        )

    def test_returns_requested_comments_page(self):
        comments_page, liked_comments = get_article_comments_page(
            article=self.article, page_number=1, user=None
        )

        self.assertEqual(comments_page.number, 1)
        self.assertTrue(comments_page.has_next())
        self.assertEqual(comments_page.next_page_number(), 2)
        self.assertEqual(
            [comment.id for comment in comments_page.object_list],
            [self.comment3.id, self.comment2.id],
        )
        self.assertEqual(liked_comments, set())

    def test_returns_next_comments_page(self):
        comments_page, liked_comments = get_article_comments_page(
            article=self.article, page_number=2, user=None
        )

        self.assertEqual(comments_page.number, 2)
        self.assertFalse(comments_page.has_next())
        self.assertEqual(
            [comment.id for comment in comments_page.object_list], [self.comment1.id]
        )
        self.assertEqual(liked_comments, set())

    def test_returns_liked_comments_for_authenticated_user_on_current_page_only(self):
        self.comment1.users_that_liked.add(self.user)
        self.comment3.users_that_liked.add(self.user)

        comments_page, liked_comments = get_article_comments_page(
            article=self.article, page_number=1, user=self.user
        )

        self.assertEqual(
            [comment.id for comment in comments_page.object_list],
            [self.comment3.id, self.comment2.id],
        )
        self.assertEqual(liked_comments, {self.comment3.id})

    def test_invalid_page_number_falls_back_to_valid_page(self):
        comments_page, liked_comments = get_article_comments_page(
            article=self.article, page_number="invalid", user=None
        )

        self.assertEqual(comments_page.number, 1)
        self.assertEqual(liked_comments, set())

    def test_out_of_range_page_number_returns_last_page(self):
        comments_page, liked_comments = get_article_comments_page(
            article=self.article, page_number=999, user=None
        )

        self.assertEqual(comments_page.number, 2)
        self.assertEqual(
            [comment.id for comment in comments_page.object_list], [self.comment1.id]
        )
        self.assertEqual(liked_comments, set())


class TestSyncArticleCommentsCount(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.commenter = User.objects.create_user(
            username="commenter", email="commenter@test.com"
        )
        self.article = Article.objects.create(
            title="Article", slug="article", author=self.author, comments_count=0
        )

    def test_repairs_too_low_count(self):
        ArticleComment.objects.create(
            article=self.article, author=self.commenter, text="First comment"
        )
        ArticleComment.objects.create(
            article=self.article, author=self.commenter, text="Second comment"
        )
        Article.objects.filter(pk=self.article.pk).update(comments_count=0)

        sync_article_comments_count(batch_size=1)

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 2)

    def test_repairs_too_high_count(self):
        ArticleComment.objects.create(
            article=self.article, author=self.commenter, text="Comment"
        )
        Article.objects.filter(pk=self.article.pk).update(comments_count=10)

        sync_article_comments_count(batch_size=1)

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 1)
