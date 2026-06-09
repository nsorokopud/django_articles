from unittest.mock import ANY, MagicMock, Mock, call, patch

from django.conf import settings
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase
from django_redis import get_redis_connection
from redis import RedisError

from articles.cache.view_counts import (
    ARTICLE_UNIQUE_VIEW_KEY,
    ARTICLE_UNSYNCED_VIEWS_KEY,
    REGISTER_ARTICLE_VIEW_LUA,
    VIEWED_ARTICLES_SET_KEY,
    _claim_view_deltas,
    _decode_article_ids,
    _restore_view_deltas,
    _sync_article_batch,
    get_cached_article_views,
    register_article_view,
    sync_article_views,
)
from tests.cache_settings import override_settings_with_redis_cache


class TestGetCachedArticleViews(SimpleTestCase):
    @patch("articles.cache.view_counts.logger.warning")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_redis_error(self, mock_get_redis, mock_warning):
        mock_redis = Mock()
        mock_redis.get.side_effect = RedisError("Redis error")
        mock_get_redis.return_value = mock_redis
        article_id = 1234

        result = get_cached_article_views(article_id)

        self.assertEqual(result, 0)
        mock_warning.assert_called_once_with(
            "Could not get cached views for article %s: %s",
            article_id,
            mock_redis.get.side_effect,
        )

    @patch("articles.cache.view_counts.get_redis_connection")
    def test_none_views(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        self.assertEqual(get_cached_article_views(1234), 0)

    @patch("articles.cache.view_counts.get_redis_connection")
    def test_correct_case(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.get.return_value = "42"
        mock_get_redis.return_value = mock_redis

        self.assertEqual(get_cached_article_views(1234), 42)


class TestRegisterArticleView(SimpleTestCase):
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_returns_false_when_unique_view_already_exists(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.eval.return_value = 0
        mock_get_redis.return_value = mock_redis

        result = register_article_view(
            article_id=123,
            viewer_id="user:1",
            unique_view_timeout=3600,
        )

        self.assertFalse(result)

        unique_key = ARTICLE_UNIQUE_VIEW_KEY.format(article_id=123, viewer_id="user:1")
        delta_key = ARTICLE_UNSYNCED_VIEWS_KEY.format(id=123)

        mock_redis.eval.assert_called_once_with(
            REGISTER_ARTICLE_VIEW_LUA,
            3,
            unique_key,
            delta_key,
            VIEWED_ARTICLES_SET_KEY,
            3600,
            123,
        )

    @patch("articles.cache.view_counts.get_redis_connection")
    def test_registers_new_unique_view(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.eval.return_value = 1
        mock_get_redis.return_value = mock_redis

        result = register_article_view(
            article_id=123,
            viewer_id="user:1",
            unique_view_timeout=3600,
        )

        self.assertTrue(result)

        unique_key = ARTICLE_UNIQUE_VIEW_KEY.format(article_id=123, viewer_id="user:1")
        delta_key = ARTICLE_UNSYNCED_VIEWS_KEY.format(id=123)

        mock_redis.eval.assert_called_once_with(
            REGISTER_ARTICLE_VIEW_LUA,
            3,
            unique_key,
            delta_key,
            VIEWED_ARTICLES_SET_KEY,
            3600,
            123,
        )

    @patch("articles.cache.view_counts.logger.error")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_returns_false_on_redis_error(self, mock_get_redis, mock_error):
        mock_redis = Mock()
        mock_redis.eval.side_effect = RedisError("Redis error")
        mock_get_redis.return_value = mock_redis

        result = register_article_view(
            article_id=123,
            viewer_id="user:1",
            unique_view_timeout=3600,
        )

        self.assertFalse(result)
        mock_error.assert_called_once_with(
            "Redis error while registering view for article %s and viewer %s: %s",
            123,
            "user:1",
            mock_redis.eval.side_effect,
        )

    @patch("articles.cache.view_counts.get_redis_connection")
    def test_passes_expected_keys_and_args_to_eval(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.eval.return_value = 1
        mock_get_redis.return_value = mock_redis

        result = register_article_view(
            article_id=999,
            viewer_id="anon:abc",
            unique_view_timeout=120,
        )

        self.assertTrue(result)

        mock_redis.eval.assert_called_once_with(
            REGISTER_ARTICLE_VIEW_LUA,
            3,
            "articles:999:unique_view:anon:abc",
            "articles:999:views_delta",
            "articles:viewed_to_sync",
            120,
            999,
        )


class TestClaimAndRestoreViewDeltas(SimpleTestCase):
    @patch("articles.cache.view_counts.logger.error")
    def test_claim_view_deltas_requeues_article_on_redis_error(self, mock_error):
        mock_redis = Mock()
        mock_redis.getdel.side_effect = [b"3", RedisError("error"), None]

        result = _claim_view_deltas(mock_redis, [1, 2, 3])

        self.assertEqual(result, {1: 3})
        mock_error.assert_called_once_with(
            "Redis error when claiming views for article %s: %s", 2, ANY
        )
        mock_redis.sadd.assert_called_once_with(VIEWED_ARTICLES_SET_KEY, 2)

    @patch("articles.cache.view_counts.logger.error")
    def test_claim_view_deltas_logs_when_requeue_also_fails(self, mock_error):
        mock_redis = Mock()
        mock_redis.getdel.side_effect = RedisError("claim failed")
        mock_redis.sadd.side_effect = RedisError("requeue failed")

        result = _claim_view_deltas(mock_redis, [7])

        self.assertEqual(result, {})
        self.assertEqual(mock_error.call_count, 2)
        mock_error.assert_has_calls(
            [
                call(
                    "Redis error when claiming views for article %s: %s",
                    7,
                    ANY,
                ),
                call(
                    "Could not re-queue article %s after failed delta claim.",
                    7,
                ),
            ]
        )

    @patch("articles.cache.view_counts.logger.warning")
    def test_claim_view_deltas_skips_invalid_values(self, mock_warning):
        mock_redis = Mock()
        mock_redis.getdel.side_effect = [b"10", b"abc", b"0"]

        result = _claim_view_deltas(mock_redis, [1, 2, 3])

        self.assertEqual(result, {1: 10})
        mock_warning.assert_called_once_with(
            "Invalid view delta value for article %s: %s",
            2,
            ANY,
        )

    def test_restore_view_deltas_returns_true_for_empty_input(self):
        self.assertTrue(_restore_view_deltas(Mock(), {}))

    @patch("articles.cache.view_counts.logger.error")
    def test_restore_view_deltas_returns_false_on_redis_error(self, mock_error):
        mock_redis = Mock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__.return_value = mock_pipe
        mock_pipe.__exit__.return_value = None
        mock_pipe.execute.side_effect = RedisError("Redis error")
        mock_redis.pipeline.return_value = mock_pipe

        result = _restore_view_deltas(mock_redis, {111: 5, 222: 9})

        self.assertFalse(result)
        mock_error.assert_called_once_with(
            "Redis error when restoring claimed view deltas: %s",
            ANY,
        )

    def test_restore_view_deltas_writes_back_values_and_requeues(self):
        mock_redis = Mock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__.return_value = mock_pipe
        mock_pipe.__exit__.return_value = None
        mock_redis.pipeline.return_value = mock_pipe

        result = _restore_view_deltas(mock_redis, {111: 5, 222: 9})

        self.assertTrue(result)
        self.assertEqual(
            mock_pipe.incrby.call_args_list,
            [
                call(ARTICLE_UNSYNCED_VIEWS_KEY.format(id=111), 5),
                call(ARTICLE_UNSYNCED_VIEWS_KEY.format(id=222), 9),
            ],
        )
        self.assertEqual(
            mock_pipe.sadd.call_args_list,
            [
                call(VIEWED_ARTICLES_SET_KEY, 111),
                call(VIEWED_ARTICLES_SET_KEY, 222),
            ],
        )
        mock_pipe.execute.assert_called_once()


class TestSyncArticleViews(TestCase):
    @patch("articles.cache.view_counts.logger.info")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_no_articles(self, mock_get_redis, mock_info):
        mock_redis = Mock()
        mock_redis.spop.return_value = []
        mock_get_redis.return_value = mock_redis

        sync_article_views()

        mock_redis.spop.assert_called_with(
            VIEWED_ARTICLES_SET_KEY, settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE
        )
        mock_info.assert_called_with("No articles to sync; exiting on batch %d.", 0)

    @patch("articles.cache.view_counts.logger.error")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_breaks_on_spop_redis_error(self, mock_get_redis, mock_error):
        mock_redis = Mock()
        mock_redis.spop.side_effect = RedisError("error")
        mock_get_redis.return_value = mock_redis

        sync_article_views()

        mock_error.assert_called_once_with(
            "Redis error when popping article IDs to sync: %s",
            mock_redis.spop.side_effect,
        )

    def test_decode_article_ids(self):
        encoded_ids = [b"9991", b"9992", b"9993"]
        self.assertEqual(_decode_article_ids(encoded_ids), [9991, 9992, 9993])

        encoded_ids = [b"9991", b"abc"]
        with patch("articles.cache.view_counts.logger") as mock_logger:
            self.assertEqual(_decode_article_ids(encoded_ids), [9991])
            mock_logger.warning.assert_called_once_with(
                "Skipping invalid article ID: %s (%s)",
                b"abc",
                ANY,
            )
            self.assertIsInstance(
                mock_logger.warning.call_args_list[0][0][2],
                ValueError,
            )

    @patch("articles.cache.view_counts._sync_article_batch")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_no_valid_article_ids(self, mock_get_redis, mock_sync):
        mock_redis = Mock()
        mock_redis.spop.side_effect = [{b"abc", b"xyz"}, set()]
        mock_get_redis.return_value = mock_redis

        with patch("articles.cache.view_counts.logger") as mock_logger:
            sync_article_views()

        mock_sync.assert_not_called()
        self.assertEqual(
            mock_logger.info.call_args_list,
            [
                call("No valid article IDs in batch %d.", 0),
                call("No articles to sync; exiting on batch %d.", 1),
            ],
        )

    @patch("articles.cache.view_counts.logger.critical")
    @patch("articles.cache.view_counts._restore_view_deltas")
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_db_error_when_syncing_views_and_restore_fails(
        self,
        mock_increment,
        mock_restore,
        mock_critical,
    ):
        article_ids = [9999]
        mock_redis = Mock()
        mock_increment.side_effect = DatabaseError("DB error")
        mock_restore.return_value = False

        with patch(
            "articles.cache.view_counts._claim_view_deltas", return_value={9999: 7}
        ):
            _sync_article_batch(article_ids, 0, mock_redis)

        mock_restore.assert_called_once_with(mock_redis, {9999: 7})
        mock_critical.assert_called_once_with(
            "Failed to restore claimed article view deltas after DB failure. "
            "View deltas may be lost for article IDs: %s",
            [9999],
        )

    @patch("articles.cache.view_counts.logger.error")
    @patch("articles.cache.view_counts._restore_view_deltas")
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_db_error_when_syncing_views_and_restore_succeeds(
        self,
        mock_increment,
        mock_restore,
        mock_error,
    ):
        article_ids = [9999]
        mock_redis = Mock()
        mock_increment.side_effect = DatabaseError("DB error")
        mock_restore.return_value = True

        with patch(
            "articles.cache.view_counts._claim_view_deltas", return_value={9999: 7}
        ):
            _sync_article_batch(article_ids, 0, mock_redis)

        mock_restore.assert_called_once_with(mock_redis, {9999: 7})
        mock_error.assert_called_once_with(
            "DB update failed. Restoring claimed article view deltas. Error: %s",
            ANY,
        )

    @override_settings_with_redis_cache()
    @patch("articles.cache.view_counts.logger.info")
    @patch("articles.cache.view_counts.logger.warning")
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_invalid_claimed_view_deltas_are_logged_and_dropped(
        self, mock_increment, mock_warning, mock_info
    ):
        r = get_redis_connection("default")
        r.flushdb()

        view_deltas = {9991: 3, 9992: "abc"}
        keys = {
            article_id: ARTICLE_UNSYNCED_VIEWS_KEY.format(id=article_id)
            for article_id in view_deltas
        }

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            pipe.execute()

        sync_article_views()

        mock_increment.assert_called_once_with({9991: 3})
        mock_warning.assert_called_once_with(
            "Invalid view delta value for article %s: %s",
            9992,
            ANY,
        )
        mock_info.assert_has_calls(
            [
                call("Synced views for %d articles in batch %d.", 1, 0),
                call("No articles to sync; exiting on batch %d.", 1),
            ]
        )

        self.assertFalse(r.smembers(VIEWED_ARTICLES_SET_KEY))
        self.assertTrue(all(r.get(key) is None for key in keys.values()))

        r.flushdb()

    @override_settings_with_redis_cache()
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_synced_view_delta_key_is_cleared_after_claim(self, mock_increment):
        r = get_redis_connection("default")
        r.flushdb()

        key = ARTICLE_UNSYNCED_VIEWS_KEY.format(id=9991)
        r.set(key, 10)
        r.sadd(VIEWED_ARTICLES_SET_KEY, 9991)

        sync_article_views()

        mock_increment.assert_called_once_with({9991: 10})
        self.assertIsNone(r.get(key))

        r.flushdb()

    @override_settings_with_redis_cache()
    @patch("articles.cache.view_counts.logger.info")
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_single_batch(self, mock_increment, mock_info):
        r = get_redis_connection("default")
        r.flushdb()

        view_deltas = {9991: 3, 9992: 0, 9993: 10}
        keys = {
            article_id: ARTICLE_UNSYNCED_VIEWS_KEY.format(id=article_id)
            for article_id in view_deltas
        }

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            pipe.execute()

        sync_article_views()

        expected_args = {k: v for k, v in view_deltas.items() if v > 0}
        mock_increment.assert_called_once_with(expected_args)
        self.assertFalse(r.smembers(VIEWED_ARTICLES_SET_KEY))
        self.assertTrue(all(r.get(key) is None for key in keys.values()))

        mock_info.assert_has_calls(
            [
                call("Synced views for %d articles in batch %d.", 2, 0),
                call("No articles to sync; exiting on batch %d.", 1),
            ]
        )

        r.flushdb()

    @override_settings_with_redis_cache(ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE=2)
    @patch("articles.cache.view_counts.logger.info")
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_multiple_batches(self, mock_increment, mock_info):
        r = get_redis_connection("default")
        r.flushdb()

        view_deltas = {9991: 3, 9992: 1, 9993: 0, 9994: 0, 9995: 10}
        keys = {
            article_id: ARTICLE_UNSYNCED_VIEWS_KEY.format(id=article_id)
            for article_id in view_deltas
        }

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            pipe.execute()

        with patch("redis.commands.core.SetCommands.spop") as mock_spop:
            mock_spop.side_effect = [
                [b"9991", b"9992"],
                [b"9993", b"9994"],
                [b"9995"],
                [],
            ]
            sync_article_views()

        self.assertEqual(
            mock_increment.call_args_list,
            [
                call({9991: 3, 9992: 1}),
                call({9995: 10}),
            ],
        )
        self.assertTrue(all(r.get(key) is None for key in keys.values()))

        self.assertCountEqual(
            mock_info.call_args_list,
            [
                call("Synced views for %d articles in batch %d.", 2, 0),
                call(
                    "No positive view deltas in batch %d for article IDs: %s",
                    1,
                    [9993, 9994],
                ),
                call("Synced views for %d articles in batch %d.", 1, 2),
                call("No articles to sync; exiting on batch %d.", 3),
            ],
        )

        r.flushdb()

    @patch("articles.cache.view_counts._decode_article_ids")
    @patch("articles.cache.view_counts._sync_article_batch")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_max_iterations(self, mock_get_redis, mock_sync, mock_decode):
        mock_redis = Mock()
        article_ids = list(range(settings.ARTICLES_VIEW_COUNT_SYNC_MAX_ITERATIONS + 1))
        mock_redis.spop.return_value = True
        mock_get_redis.return_value = mock_redis
        mock_decode.side_effect = [
            [aid] * settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE
            for aid in article_ids
        ]

        sync_article_views()

        self.assertEqual(
            len(mock_sync.call_args_list),
            settings.ARTICLES_VIEW_COUNT_SYNC_MAX_ITERATIONS,
        )
        for i, _call in enumerate(mock_sync.call_args_list):
            self.assertEqual(
                _call,
                call(
                    [article_ids[i]] * settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE,
                    i,
                    mock_redis,
                ),
            )
        self.assertNotIn(
            call(
                [article_ids[-1]] * settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE,
                ANY,
                ANY,
            ),
            mock_sync.call_args_list,
        )
