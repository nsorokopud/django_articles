from unittest.mock import ANY, Mock, call, patch

from celery.exceptions import Retry
from django.test import SimpleTestCase, override_settings

from articles.tasks import (
    ARTICLE_MEDIA_CLEANUP_LOCK_KEY,
    ARTICLE_SYNC_COMMENT_COUNTS_LOCK_KEY,
    ARTICLE_SYNC_LIKES_LOCK_KEY,
    ARTICLE_SYNC_VIEWS_LOCK_KEY,
    COMMENT_SYNC_LIKES_LOCK_KEY,
    cleanup_unused_article_inline_media_task,
    delete_article_media_task,
    sync_article_comments_count_task,
    sync_article_likes_count_task,
    sync_article_views_task,
    sync_comment_likes_count_task,
)


class LockedTaskTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()

        self.cache_lock_patcher = patch("articles.tasks.cache_lock")
        self.mock_cache_lock = self.cache_lock_patcher.start()
        self.addCleanup(self.cache_lock_patcher.stop)

    def set_lock_acquired(self):
        self.mock_cache_lock.return_value.__enter__.return_value = Mock(acquired=True)

    def set_lock_not_acquired(self):
        self.mock_cache_lock.return_value.__enter__.return_value = Mock(acquired=False)

    def assert_lock_released_once(self):
        self.mock_cache_lock.return_value.__exit__.assert_called_once()

    def assert_lock_not_released(self):
        self.mock_cache_lock.return_value.__exit__.assert_not_called()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestSyncArticleViewsTask(LockedTaskTestCase):
    @patch("articles.tasks.logger")
    @patch("articles.cache.view_counts.sync_article_views")
    def test_sync_article_views_task_runs_and_updates_views(
        self, mock_sync, mock_logger
    ):
        self.set_lock_acquired()

        result = sync_article_views_task.apply(args=()).get()

        self.assertIsNone(result)
        self.mock_cache_lock.assert_called_once_with(
            lock_key=ARTICLE_SYNC_VIEWS_LOCK_KEY, lock_value=ANY, timeout=600
        )
        mock_sync.assert_called_once()
        mock_logger.info.assert_any_call("Updated article view counts.")
        self.assert_lock_released_once()

    @patch("articles.tasks.logger")
    @patch("articles.cache.view_counts.sync_article_views")
    def test_sync_article_views_task_skips_when_lock_exists(
        self, mock_sync, mock_logger
    ):
        self.set_lock_not_acquired()

        result = sync_article_views_task.apply(args=()).get()

        self.assertIsNone(result)
        mock_sync.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Article view sync skipped: already running."
        )
        self.assert_lock_released_once()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestSyncArticleLikesCountTask(LockedTaskTestCase):
    @patch("articles.tasks.logger")
    @patch("articles.services.likes.sync_article_likes_count")
    def test_sync_article_likes_count_task_runs(self, mock_sync, mock_logger):
        self.set_lock_acquired()

        result = sync_article_likes_count_task.apply(args=()).get()

        self.assertIsNone(result)
        self.mock_cache_lock.assert_called_once_with(
            lock_key=ARTICLE_SYNC_LIKES_LOCK_KEY, lock_value=ANY, timeout=1800
        )
        mock_sync.assert_called_once()
        mock_logger.info.assert_any_call("Synced article likes counts.")
        self.assert_lock_released_once()

    @patch("articles.tasks.logger")
    @patch("articles.services.likes.sync_article_likes_count")
    def test_sync_article_likes_count_task_skips_when_lock_exists(
        self, mock_sync, mock_logger
    ):
        self.set_lock_not_acquired()

        result = sync_article_likes_count_task.apply(args=()).get()

        self.assertIsNone(result)
        mock_sync.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Article likes sync skipped: already running."
        )
        self.assert_lock_released_once()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestSyncCommentLikesCountTask(LockedTaskTestCase):
    @patch("articles.tasks.logger")
    @patch("articles.services.likes.sync_comment_likes_count")
    def test_sync_comment_likes_count_task_runs(self, mock_sync, mock_logger):
        self.set_lock_acquired()

        result = sync_comment_likes_count_task.apply(args=()).get()

        self.assertIsNone(result)
        self.mock_cache_lock.assert_called_once_with(
            lock_key=COMMENT_SYNC_LIKES_LOCK_KEY, lock_value=ANY, timeout=1800
        )
        mock_sync.assert_called_once()
        mock_logger.info.assert_any_call("Synced comment likes counts.")
        self.assert_lock_released_once()

    @patch("articles.tasks.logger")
    @patch("articles.services.likes.sync_comment_likes_count")
    def test_sync_comment_likes_count_task_skips_when_lock_exists(
        self, mock_sync, mock_logger
    ):
        self.set_lock_not_acquired()

        result = sync_comment_likes_count_task.apply(args=()).get()

        self.assertIsNone(result)
        mock_sync.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Comment likes sync skipped: already running."
        )
        self.assert_lock_released_once()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestSyncArticleCommentsCountTask(LockedTaskTestCase):
    @patch("articles.tasks.logger")
    @patch("articles.services.comments.sync_article_comments_count")
    def test_sync_article_comments_count_task_runs(self, mock_sync, mock_logger):
        self.set_lock_acquired()

        result = sync_article_comments_count_task.apply(args=()).get()

        self.assertIsNone(result)
        self.mock_cache_lock.assert_called_once_with(
            lock_key=ARTICLE_SYNC_COMMENT_COUNTS_LOCK_KEY, lock_value=ANY, timeout=1800
        )
        mock_sync.assert_called_once_with(batch_size=1000)
        mock_logger.info.assert_any_call("Synced article comments counts.")
        self.assert_lock_released_once()

    @patch("articles.tasks.logger")
    @patch("articles.services.comments.sync_article_comments_count")
    def test_sync_article_comments_count_task_runs_with_custom_batch_size(
        self, mock_sync, mock_logger
    ):
        self.set_lock_acquired()

        result = sync_article_comments_count_task.apply(kwargs={"batch_size": 25}).get()

        self.assertIsNone(result)
        self.mock_cache_lock.assert_called_once_with(
            lock_key=ARTICLE_SYNC_COMMENT_COUNTS_LOCK_KEY, lock_value=ANY, timeout=1800
        )
        mock_sync.assert_called_once_with(batch_size=25)
        self.assert_lock_released_once()

    @patch("articles.tasks.logger")
    @patch("articles.services.comments.sync_article_comments_count")
    def test_sync_article_comments_count_task_skips_when_lock_exists(
        self, mock_sync, mock_logger
    ):
        self.set_lock_not_acquired()

        result = sync_article_comments_count_task.apply(args=()).get()

        self.assertIsNone(result)
        mock_sync.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Article comments count sync skipped: already running."
        )
        self.assert_lock_released_once()


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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestCleanupUnusedArticleInlineMediaTask(LockedTaskTestCase):
    @patch("articles.tasks.logger")
    @patch("articles.services.media.cleanup_unused_article_inline_media")
    def test_runs_until_empty_batch(self, mock_cleanup, mock_logger):
        self.set_lock_acquired()
        mock_cleanup.side_effect = [500, 25, 0]

        result = cleanup_unused_article_inline_media_task.apply(
            kwargs={"batch_size": 100, "max_batches": 10}
        ).get()

        self.assertIsNone(result)
        self.mock_cache_lock.assert_called_once_with(
            lock_key=ARTICLE_MEDIA_CLEANUP_LOCK_KEY, lock_value=ANY, timeout=3600
        )
        self.assertEqual(mock_cleanup.call_count, 3)
        mock_cleanup.assert_has_calls(
            [
                call(batch_size=100),
                call(batch_size=100),
                call(batch_size=100),
            ]
        )
        mock_logger.info.assert_any_call(
            "Cleaned up %s unused article media files.", 525
        )
        self.assert_lock_released_once()

    @patch("articles.tasks.logger")
    @patch("articles.services.media.cleanup_unused_article_inline_media")
    def test_stops_at_max_batches(self, mock_cleanup, mock_logger):
        self.set_lock_acquired()
        mock_cleanup.side_effect = [10, 10, 10]

        result = cleanup_unused_article_inline_media_task.apply(
            kwargs={"batch_size": 50, "max_batches": 3}
        ).get()

        self.assertIsNone(result)
        self.assertEqual(mock_cleanup.call_count, 3)
        mock_cleanup.assert_has_calls(
            [call(batch_size=50), call(batch_size=50), call(batch_size=50)]
        )
        mock_logger.info.assert_any_call(
            "Cleaned up %s unused article media files.", 30
        )
        self.assert_lock_released_once()

    @patch("articles.tasks.logger")
    @patch("articles.services.media.cleanup_unused_article_inline_media")
    def test_skips_when_lock_exists(self, mock_cleanup, mock_logger):
        self.set_lock_not_acquired()

        result = cleanup_unused_article_inline_media_task.apply(args=()).get()

        self.assertIsNone(result)
        mock_cleanup.assert_not_called()
        mock_logger.info.assert_called_once_with(
            "Article media cleanup skipped: already running."
        )
        self.assert_lock_released_once()

    @patch("articles.services.media.cleanup_unused_article_inline_media")
    def test_releases_lock_on_error(self, mock_cleanup):
        self.set_lock_acquired()
        mock_cleanup.side_effect = ZeroDivisionError("error")

        with self.assertRaises(ZeroDivisionError):
            cleanup_unused_article_inline_media_task.apply(args=()).get()

        self.assert_lock_released_once()
