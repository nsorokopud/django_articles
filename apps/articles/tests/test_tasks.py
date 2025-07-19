from unittest.mock import patch

from celery.exceptions import Retry
from django.test import SimpleTestCase, override_settings

from articles.tasks import delete_article_inline_media_task, sync_article_views_task


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestTasks(SimpleTestCase):
    @patch("articles.tasks.logger")
    @patch("articles.tasks.sync_article_views")
    def test_sync_article_views_task(self, mock_sync, mock_logger):
        res = sync_article_views_task()
        self.assertIsNone(res)
        mock_sync.assert_called_once()
        mock_logger.info.assert_called_once_with("Updated article view counts")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestDeleteArticleInlineMediaTask(SimpleTestCase):
    def setUp(self):
        self.article_id = 123
        self.author_id = 5

    @patch("celery.app.task.Task.request")
    @patch("articles.tasks.logger")
    @patch("articles.tasks.delete_media_files_attached_to_article")
    def test_success(self, mock_delete, mock_logger, mock_request):
        mock_request.id = 12345
        delete_article_inline_media_task.delay(self.article_id, self.author_id)

        mock_delete.assert_called_once_with(self.article_id, self.author_id)
        mock_logger.info.assert_called_once_with(
            "Deleting inline media for article %s by author %s. Task ID: %s.",
            self.article_id,
            self.author_id,
            mock_request.id,
        )

    @patch("celery.app.task.Task.request")
    @patch(
        "articles.tasks.delete_media_files_attached_to_article",
        side_effect=OSError("OS error"),
    )
    def test_retriable_exception(self, mock_delete, mock_request):
        mock_request.retries = 1
        mock_request.called_directly = False

        with self.assertRaises(Retry) as context:
            delete_article_inline_media_task.delay(self.article_id, self.author_id)

        self.assertEqual(context.exception.exc, mock_delete.side_effect)

    @patch("celery.app.task.Task.request")
    @patch(
        "articles.tasks.delete_media_files_attached_to_article",
        side_effect=ZeroDivisionError("Non-retriable"),
    )
    def test_non_retriable_exception(self, mock_delete, mock_request):
        mock_request.retries = 1
        mock_request.called_directly = False

        with self.assertRaises(ZeroDivisionError) as context:
            delete_article_inline_media_task.delay(self.article_id, self.author_id)

        self.assertEqual(context.exception, mock_delete.side_effect)
