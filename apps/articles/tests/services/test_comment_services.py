from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from articles.models import Article, ArticleComment
from articles.services.comments import create_article_comment
from users.models import User


class TestCreateArticleComment(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
        )
        self.commenter = User.objects.create_user(
            username="commenter",
            email="commenter@test.com",
        )
        self.article = Article.objects.create(
            title="article",
            slug="article",
            author=self.author,
            preview_text="preview",
            content="content",
        )

    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_creates_comment_and_dispatches_notification_when_created(
        self,
        mock_create_notification,
        mock_dispatch,
    ):
        notification = type(
            "NotificationStub",
            (),
            {"id": 123, "notification_type": "new_comment"},
        )()
        mock_create_notification.return_value = (notification, True)

        comment = create_article_comment(
            article=self.article,
            user=self.commenter,
            text="hello world",
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
            notification_id=123,
            notification_type="new_comment",
            is_new_unread=True,
        )

    @patch("articles.services.comments.dispatch_notification_after_commit")
    @patch("articles.services.comments.create_new_comment_notification")
    def test_creates_comment_and_dispatches_notification_when_unread_state_returned(
        self,
        mock_create_notification,
        mock_dispatch,
    ):
        notification = type(
            "NotificationStub",
            (),
            {"id": 456, "notification_type": "new_comment"},
        )()
        mock_create_notification.return_value = (notification, False)

        comment = create_article_comment(
            article=self.article,
            user=self.commenter,
            text="another comment",
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
            notification_id=456,
            notification_type="new_comment",
            is_new_unread=False,
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
            article=self.article,
            user=self.commenter,
            text="no notification",
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
            article=self.article,
            user=self.commenter,
            text="should persist",
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
            article=self.article,
            user=self.commenter,
            text="should also persist",
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
