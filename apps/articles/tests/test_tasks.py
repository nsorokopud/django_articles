from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from articles.tasks import sync_article_views_task


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestTasks(SimpleTestCase):
    @patch("articles.tasks.logger")
    @patch("articles.tasks.sync_article_views")
    def test_sync_article_views_task(self, mock_sync, mock_logger):
        res = sync_article_views_task()
        self.assertIsNone(res)
        mock_sync.assert_called_once()
        mock_logger.info.assert_called_once_with("Updated article view counts")
