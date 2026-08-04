from unittest.mock import ANY, MagicMock, Mock, call, patch

import pytest
from django.conf import settings
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase
from django_redis import get_redis_connection
from redis import RedisError

from articles.cache.view_counts import (
    ARTICLES_PENDING_VIEW_SYNC_KEY,
    REGISTER_VIEW_LUA,
    UNIQUE_VIEW_KEY,
    VIEW_DELTA_KEY,
    _claim_view_deltas,
    _parse_article_ids,
    _restore_claimed_view_deltas,
    _sync_article_batch,
    get_cached_article_views,
    register_article_view,
    sync_article_views,
)
from tests.cache_settings import override_settings_with_redis_cache


class TestGetCachedArticleViews(SimpleTestCase):
    @patch("articles.cache.view_counts.logger.exception")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_redis_error(self, mock_get_redis, mock_exception):
        mock_redis = Mock()
        mock_redis.get.side_effect = RedisError("Redis error")
        mock_get_redis.return_value = mock_redis
        article_id = 1234

        result = get_cached_article_views(article_id)

        self.assertEqual(result, 0)
        mock_exception.assert_called_once_with(
            "Could not get cached views for article %s", article_id
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

        unique_key = UNIQUE_VIEW_KEY.format(article_id=123, viewer_id="user:1")
        delta_key = VIEW_DELTA_KEY.format(article_id=123)

        mock_redis.eval.assert_called_once_with(
            REGISTER_VIEW_LUA,
            3,
            unique_key,
            delta_key,
            ARTICLES_PENDING_VIEW_SYNC_KEY,
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

        unique_key = UNIQUE_VIEW_KEY.format(article_id=123, viewer_id="user:1")
        delta_key = VIEW_DELTA_KEY.format(article_id=123)

        mock_redis.eval.assert_called_once_with(
            REGISTER_VIEW_LUA,
            3,
            unique_key,
            delta_key,
            ARTICLES_PENDING_VIEW_SYNC_KEY,
            3600,
            123,
        )

    @patch("articles.cache.view_counts.logger.exception")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_returns_false_on_redis_error(self, mock_get_redis, mock_exception):
        mock_redis = Mock()
        mock_redis.eval.side_effect = RedisError("Redis error")
        mock_get_redis.return_value = mock_redis

        result = register_article_view(
            article_id=123,
            viewer_id="user:1",
            unique_view_timeout=3600,
        )

        self.assertFalse(result)
        mock_exception.assert_called_once_with(
            "Could not register view (article %s, viewer %s)", 123, "user:1"
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
            REGISTER_VIEW_LUA,
            3,
            "articles:999:unique_view:anon:abc",
            "articles:999:views_delta",
            "articles:viewed_to_sync",
            120,
            999,
        )


class TestClaimAndRestoreViewDeltas(SimpleTestCase):
    @patch("articles.cache.view_counts.logger.exception")
    def test_claim_view_deltas_requeues_article_on_redis_error(self, mock_exception):
        mock_redis = Mock()
        mock_redis.getdel.side_effect = [b"3", RedisError("error"), None]

        result = _claim_view_deltas(mock_redis, [1, 2, 3])

        self.assertEqual(result, {1: 3})
        mock_exception.assert_called_once_with(
            "Could not claim views for article %s", 2
        )
        mock_redis.sadd.assert_called_once_with(ARTICLES_PENDING_VIEW_SYNC_KEY, 2)

    @patch("articles.cache.view_counts.logger.exception")
    def test_claim_view_deltas_logs_when_requeue_also_fails(self, mock_exception):
        mock_redis = Mock()
        mock_redis.getdel.side_effect = RedisError("claim failed")
        mock_redis.sadd.side_effect = RedisError("requeue failed")

        result = _claim_view_deltas(mock_redis, [7])

        self.assertEqual(result, {})
        self.assertEqual(mock_exception.call_count, 2)
        mock_exception.assert_has_calls(
            [
                call("Could not claim views for article %s", 7),
                call("Could not requeue article %s", 7),
            ]
        )

    @patch("articles.cache.view_counts.logger.warning")
    def test_claim_view_deltas_skips_invalid_values(self, mock_warning):
        mock_redis = Mock()
        mock_redis.getdel.side_effect = [b"10", b"abc", b"0"]

        result = _claim_view_deltas(mock_redis, [1, 2, 3])

        self.assertEqual(result, {1: 10})
        mock_warning.assert_called_once_with(
            "Invalid delta (%r) for article %s",
            b"abc",
            2,
        )

    def test_restore_claimed_view_deltas_returns_true_for_empty_input(self):
        self.assertTrue(_restore_claimed_view_deltas(Mock(), {}))

    @patch("articles.cache.view_counts.logger.exception")
    def test_restore_claimed_view_deltas_returns_false_on_redis_error(
        self, mock_exception
    ):
        mock_redis = Mock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__.return_value = mock_pipe
        mock_pipe.__exit__.return_value = None
        mock_pipe.execute.side_effect = RedisError("Redis error")
        mock_redis.pipeline.return_value = mock_pipe

        result = _restore_claimed_view_deltas(mock_redis, {111: 5, 222: 9})

        self.assertFalse(result)
        mock_exception.assert_called_once_with("Could not restore claimed view deltas")

    def test_restore_claimed_view_deltas_writes_back_values_and_requeues(self):
        mock_redis = Mock()
        mock_pipe = MagicMock()
        mock_pipe.__enter__.return_value = mock_pipe
        mock_pipe.__exit__.return_value = None
        mock_redis.pipeline.return_value = mock_pipe

        result = _restore_claimed_view_deltas(mock_redis, {111: 5, 222: 9})

        self.assertTrue(result)
        self.assertEqual(
            mock_pipe.incrby.call_args_list,
            [
                call(VIEW_DELTA_KEY.format(article_id=111), 5),
                call(VIEW_DELTA_KEY.format(article_id=222), 9),
            ],
        )
        self.assertEqual(
            mock_pipe.sadd.call_args_list,
            [
                call(ARTICLES_PENDING_VIEW_SYNC_KEY, 111),
                call(ARTICLES_PENDING_VIEW_SYNC_KEY, 222),
            ],
        )
        mock_pipe.execute.assert_called_once()


@pytest.mark.xdist_group(name="redis")
class TestSyncArticleViews(TestCase):
    @patch("articles.cache.view_counts.logger.debug")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_no_articles(self, mock_get_redis, mock_debug):
        mock_redis = Mock()
        mock_redis.spop.return_value = []
        mock_get_redis.return_value = mock_redis

        sync_article_views()

        mock_redis.spop.assert_called_with(
            ARTICLES_PENDING_VIEW_SYNC_KEY,
            settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE,
        )
        mock_debug.assert_called_with("No articles to sync; exiting on batch %d", 0)

    @patch("articles.cache.view_counts.logger.exception")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_breaks_on_spop_redis_error(self, mock_get_redis, mock_exception):
        mock_redis = Mock()
        mock_redis.spop.side_effect = RedisError("error")
        mock_get_redis.return_value = mock_redis

        sync_article_views()

        mock_exception.assert_called_once_with("Could not pop article IDs to sync")

    def test_parse_article_ids(self):
        encoded_ids = [b"9991", b"9992", b"9993"]
        self.assertEqual(_parse_article_ids(encoded_ids), [9991, 9992, 9993])

        encoded_ids = [b"9991", b"abc"]
        with patch("articles.cache.view_counts.logger") as mock_logger:
            self.assertEqual(_parse_article_ids(encoded_ids), [9991])
            mock_logger.warning.assert_called_once_with(
                "Skipping invalid article ID: %r",
                b"abc",
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
                call("No valid article IDs in batch %d", 0),
            ],
        )
        mock_logger.debug.assert_called_once_with(
            "No articles to sync; exiting on batch %d", 1
        )

    @patch("articles.cache.view_counts.logger.error")
    @patch("articles.cache.view_counts._restore_claimed_view_deltas")
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_db_error_when_syncing_views_and_restore_fails(
        self,
        mock_increment,
        mock_restore,
        mock_error,
    ):
        article_ids = [9999]
        mock_redis = Mock()
        mock_increment.side_effect = DatabaseError("DB error")
        mock_restore.return_value = False

        with patch(
            "articles.cache.view_counts._claim_view_deltas", return_value={9999: 7}
        ):
            _sync_article_batch(mock_redis, article_ids, 0)

        mock_restore.assert_called_once_with(mock_redis, {9999: 7})
        mock_error.assert_called_once_with(
            "View deltas may be lost for articles: %s", [9999]
        )

    @patch("articles.cache.view_counts.logger.error")
    @patch("articles.cache.view_counts._restore_claimed_view_deltas")
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
            _sync_article_batch(mock_redis, article_ids, 0)

        mock_restore.assert_called_once_with(mock_redis, {9999: 7})
        mock_error.assert_not_called()

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
            article_id: VIEW_DELTA_KEY.format(article_id=article_id)
            for article_id in view_deltas
        }

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(ARTICLES_PENDING_VIEW_SYNC_KEY, article_id)
            pipe.execute()

        sync_article_views()

        mock_increment.assert_called_once_with({9991: 3})
        mock_warning.assert_called_once_with(
            "Invalid delta (%r) for article %s",
            b"abc",
            9992,
        )
        mock_info.assert_has_calls(
            [
                call("Synced views for %d articles in batch %d", 1, 0),
            ]
        )

        self.assertFalse(r.smembers(ARTICLES_PENDING_VIEW_SYNC_KEY))
        self.assertTrue(all(r.get(key) is None for key in keys.values()))

        r.flushdb()

    @override_settings_with_redis_cache()
    @patch("articles.cache.view_counts.bulk_increment_article_view_counts")
    def test_synced_view_delta_key_is_cleared_after_claim(self, mock_increment):
        r = get_redis_connection("default")
        r.flushdb()

        key = VIEW_DELTA_KEY.format(article_id=9991)
        r.set(key, 10)
        r.sadd(ARTICLES_PENDING_VIEW_SYNC_KEY, 9991)

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
            article_id: VIEW_DELTA_KEY.format(article_id=article_id)
            for article_id in view_deltas
        }

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(ARTICLES_PENDING_VIEW_SYNC_KEY, article_id)
            pipe.execute()

        sync_article_views()

        expected_args = {k: v for k, v in view_deltas.items() if v > 0}
        mock_increment.assert_called_once_with(expected_args)
        self.assertFalse(r.smembers(ARTICLES_PENDING_VIEW_SYNC_KEY))
        self.assertTrue(all(r.get(key) is None for key in keys.values()))

        mock_info.assert_called_once_with(
            "Synced views for %d articles in batch %d", 2, 0
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
            article_id: VIEW_DELTA_KEY.format(article_id=article_id)
            for article_id in view_deltas
        }

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(ARTICLES_PENDING_VIEW_SYNC_KEY, article_id)
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
                call("Synced views for %d articles in batch %d", 2, 0),
                call("Synced views for %d articles in batch %d", 1, 2),
            ],
        )

        r.flushdb()

    @patch("articles.cache.view_counts._parse_article_ids")
    @patch("articles.cache.view_counts._sync_article_batch")
    @patch("articles.cache.view_counts.get_redis_connection")
    def test_max_iterations(self, mock_get_redis, mock_sync, mock_parse):
        mock_redis = Mock()
        article_ids = list(range(settings.ARTICLES_VIEW_COUNT_SYNC_MAX_ITERATIONS + 1))
        mock_redis.spop.return_value = True
        mock_get_redis.return_value = mock_redis
        mock_parse.side_effect = [
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
                    mock_redis,
                    [article_ids[i]] * settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE,
                    i,
                ),
            )
        self.assertNotIn(
            call(
                mock_redis,
                [article_ids[-1]] * settings.ARTICLES_VIEW_COUNT_SYNC_MAX_BATCH_SIZE,
                ANY,
            ),
            mock_sync.call_args_list,
        )
