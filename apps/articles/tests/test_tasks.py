from unittest.mock import patch

from celery.exceptions import Retry
from django.test import SimpleTestCase, override_settings

from articles.tasks import delete_article_media_task, sync_article_views_task


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestSyncArticleViewsTask(SimpleTestCase):
    @patch("articles.tasks.cache")
    @patch("articles.tasks.logger")
    @patch("articles.cache.view_counts.sync_article_views")
    def test_sync_article_views_task_runs_and_updates_views(
        self, mock_sync, mock_logger, mock_cache
    ):
        mock_cache.add.return_value = True
        mock_cache.get.side_effect = lambda key: mock_cache.add.call_args.args[1]

        result = sync_article_views_task.apply(args=()).get()

        self.assertIsNone(result)
        mock_cache.add.assert_called_once()
        mock_sync.assert_called_once()
        mock_logger.info.assert_any_call("Updated article view counts.")
        mock_cache.get.assert_called_once()
        mock_cache.delete.assert_called_once()

    @patch("articles.tasks.cache")
    @patch("articles.tasks.logger")
    @patch("articles.cache.view_counts.sync_article_views")
    def test_sync_article_views_task_skips_when_lock_exists(
        self, mock_sync, mock_logger, mock_cache
    ):
        mock_cache.add.return_value = False

        result = sync_article_views_task.apply(args=()).get()

        self.assertIsNone(result)
        mock_sync.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Article view sync skipped: already running."
        )
        mock_cache.delete.assert_not_called()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestDeleteArticleMediaTask(SimpleTestCase):
    def setUp(self):
        self.article_id = 123
        self.author_id = 5
        self.preview_image_name = "preview.jpg"

    @patch("celery.app.task.Task.request")
    @patch("articles.services.media.delete_article_media_files")
    def test_success(self, mock_delete, mock_request):
        mock_request.id = 12345
        delete_article_media_task.delay(
            article_id=self.article_id,
            author_id=self.author_id,
            preview_image_name=self.preview_image_name,
        )

        mock_delete.assert_called_once_with(
            article_id=self.article_id,
            author_id=self.author_id,
            preview_image_name=self.preview_image_name,
        )

    @patch("celery.app.task.Task.request")
    @patch(
        "articles.services.media.delete_article_media_files",
        side_effect=OSError("OS error"),
    )
    def test_retriable_exception(self, mock_delete, mock_request):
        mock_request.retries = 1
        mock_request.called_directly = False

        with self.assertRaises(Retry) as context:
            delete_article_media_task.delay(self.article_id, self.author_id, "")

        self.assertEqual(context.exception.exc, mock_delete.side_effect)

    @patch("celery.app.task.Task.request")
    @patch(
        "articles.services.media.delete_article_media_files",
        side_effect=ZeroDivisionError("Non-retriable"),
    )
    def test_non_retriable_exception(self, mock_delete, mock_request):
        mock_request.retries = 1
        mock_request.called_directly = False

        with self.assertRaises(ZeroDivisionError) as context:
            delete_article_media_task.delay(self.article_id, self.author_id, "")

        self.assertEqual(context.exception, mock_delete.side_effect)
