from unittest.mock import ANY, MagicMock, Mock, call, patch

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings
from django_redis import get_redis_connection
from redis import RedisError

from articles.cache import (
    ARTICLE_VIEWS_KEY,
    VIEWED_ARTICLES_RETRY_SET_KEY,
    VIEWED_ARTICLES_SET_KEY,
    _decode_article_ids,
    _remove_synced_view_deltas_from_cache,
    _sync_article_batch,
    get_cached_article_views,
    increment_cached_article_views,
    sync_article_views,
)
from articles.settings import (
    ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE,
    ARTICLE_VIEW_SYNC_MAX_ITERATIONS,
)
from config.settings import CACHES


class TestGetCachedArticleViews(SimpleTestCase):
    @patch("articles.cache.logger.warning")
    @patch("articles.cache.get_redis_connection")
    def test_redis_error(self, mock_get_redis, mock_warning):
        mock_redis = Mock()
        mock_redis.get.side_effect = RedisError("Redis error")
        mock_get_redis.return_value = mock_redis
        article_id = 1234

        get_cached_article_views(article_id)
        mock_warning.assert_called_once_with(
            "Could not get cached views for article %s: %s",
            article_id,
            mock_redis.get.side_effect,
        )

    @patch("articles.cache.get_redis_connection")
    def test_none_views(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis
        article_id = 1234

        self.assertEqual(get_cached_article_views(article_id), 0)

    @patch("articles.cache.get_redis_connection")
    def test_correct_case(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.get.return_value = "42"
        mock_get_redis.return_value = mock_redis
        article_id = 1234

        self.assertEqual(get_cached_article_views(article_id), 42)


class TestIncrementCachedArticleViews(SimpleTestCase):
    @patch("articles.cache.logger.error")
    @patch("articles.cache.get_redis_connection")
    def test_redis_error(self, mock_get_redis, mock_error):
        mock_redis = Mock()
        mock_redis.incr.side_effect = RedisError("Redis error")
        mock_get_redis.return_value = mock_redis
        article_id = 1234

        increment_cached_article_views(article_id)
        mock_error.assert_called_once_with(
            "Redis error when incrementing views for article %s: %s",
            article_id,
            mock_redis.incr.side_effect,
        )

    @patch("articles.cache.get_redis_connection")
    def test_correct_case(self, mock_get_redis):
        mock_redis = Mock()
        mock_get_redis.return_value = mock_redis
        article_id = 1234

        increment_cached_article_views(article_id)
        mock_redis.incr.assert_called_once_with(ARTICLE_VIEWS_KEY.format(id=article_id))
        mock_redis.sadd.assert_called_once_with(VIEWED_ARTICLES_SET_KEY, article_id)


class TestSyncArticleViews(TestCase):
    @patch("articles.cache.logger.info")
    @patch("articles.cache.get_redis_connection")
    def test_no_articles(self, mock_get_redis, mock_info):
        mock_redis = Mock()
        mock_redis.spop.return_value = []
        mock_redis.smembers.return_value = set()
        mock_get_redis.return_value = mock_redis

        sync_article_views()
        mock_redis.spop.assert_called_with(
            VIEWED_ARTICLES_SET_KEY, ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE
        )
        mock_info.assert_called_with("No articles to sync; exiting on batch %d.", 0)

    def test_decode_article_ids(self):
        encoded_ids = [b"9991", b"9992", b"9993"]
        self.assertEqual(_decode_article_ids(encoded_ids), [9991, 9992, 9993])

        encoded_ids = [b"9991", b"abc"]
        with patch("articles.cache.logger") as mock_logger:
            self.assertEqual(_decode_article_ids(encoded_ids), [9991])
            mock_logger.warning.assert_called_once_with(
                "Skipping invalid article ID: %s (%s)",
                b"abc",
                ANY,
            )
            self.assertIsInstance(
                mock_logger.warning.call_args_list[0][0][2], ValueError
            )

    @patch("articles.cache.get_redis_connection")
    def test_no_valid_article_ids(self, mock_get_redis):
        mock_redis = Mock()
        mock_redis.spop.side_effect = [{b"abc", b"xyz"}, set()]
        mock_get_redis.return_value = mock_redis

        with (
            patch("articles.cache._requeue_failed_view_syncs"),
            patch("articles.cache._sync_article_batch") as mock_sync,
            patch("articles.cache.logger") as mock_logger,
        ):

            sync_article_views()
            mock_sync.assert_not_called()
            self.assertEqual(
                mock_logger.info.call_args_list,
                [
                    call("No valid article IDs in batch %s.", 0),
                    call("No articles to sync; exiting on batch %d.", 1),
                ],
            )

    @override_settings(CACHES=CACHES)
    @patch("articles.cache.logger.info")
    @patch("articles.cache.logger.warning")
    @patch("articles.cache.bulk_increment_article_view_counts")
    def test_skips_invalid_view_deltas(self, mock_increment, mock_warning, mock_info):
        r = get_redis_connection("default")
        r.flushdb()

        view_deltas = {9991: 3, 9992: "abc"}
        keys = {id: ARTICLE_VIEWS_KEY.format(id=id) for id in view_deltas}

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            pipe.execute()

        with r.pipeline() as pipe:
            [pipe.get(keys[article_id]) for article_id in view_deltas]
            view_counts = pipe.execute()
        self.assertFalse(any(vc is None for vc in view_counts))

        sync_article_views()
        expected_args = {9991: 3}
        mock_increment.assert_called_once_with(expected_args)
        mock_warning.assert_called_once_with(
            "Invalid view delta value for key %s: %s",
            ARTICLE_VIEWS_KEY.format(id=9992),
            ANY,
        )
        self.assertIsInstance(mock_warning.call_args[0][2], ValueError)
        mock_info.assert_has_calls(
            [
                call("Synced views for %d articles in batch %s.", 1, 0),
                call("No articles to sync; exiting on batch %d.", 1),
            ]
        )

        viewed_articles = r.smembers(VIEWED_ARTICLES_SET_KEY)
        self.assertFalse(viewed_articles)

        with r.pipeline() as pipe:
            [pipe.get(keys[article_id]) for article_id in view_deltas]
            view_counts = pipe.execute()
        self.assertTrue(all(vc is None for vc in view_counts))

        r.flushdb()

    @patch("articles.cache._remove_synced_view_deltas_from_cache")
    @patch("articles.cache.get_redis_connection")
    @patch("articles.cache.logger")
    def test_redis_error_when_getting_views(
        self, mock_logger, mock_get_redis, mock_remove
    ):
        mock_get_redis.return_value.spop.side_effect = [{b"9999"}, set()]
        mock_get_redis.return_value.pipeline.side_effect = RedisError("pipeline failed")

        sync_article_views()
        mock_remove.assert_called_once_with(ANY, [9999])

        mock_logger.error.assert_called_once_with(
            "Redis error when getting views for articles %s: %s", [9999], ANY
        ),

        self.assertEqual(
            mock_logger.info.call_args_list,
            [
                call("Re-queued %d failed article view syncs", 0),
                call(
                    "No positive view deltas in batch %s for article IDs: %s",
                    0,
                    [9999],
                ),
                call("No articles to sync; exiting on batch %d.", 1),
            ],
        )
        mock_remove.assert_called_once_with(mock_get_redis.return_value, [9999])

    @patch("articles.cache.logger")
    @patch("articles.cache._remove_synced_view_deltas_from_cache")
    @patch("articles.cache.bulk_increment_article_view_counts")
    @patch("articles.cache._get_view_delta_values_from_cache")
    def test_db_error_when_syncing_views(
        self,
        mock_get_view_delta,
        mock_increment,
        mock_remove,
        mock_logger,
    ):
        article_ids = [9999]
        mock_redis = Mock()
        mock_get_view_delta.return_value = article_ids
        mock_increment.side_effect = DatabaseError("DB error")

        _sync_article_batch(article_ids, 0, mock_redis)

        mock_redis.sadd.assert_called_once_with(
            VIEWED_ARTICLES_RETRY_SET_KEY, *article_ids
        )
        mock_logger.error.assert_called_once_with(
            "DB update failed. Re-queuing article IDs for retry. Error: %s", ANY
        )
        self.assertIsInstance(mock_logger.error.call_args_list[0][0][1], DatabaseError)
        mock_remove.assert_not_called()

    @patch("articles.cache.logger")
    @patch("articles.cache.get_redis_connection")
    def test_redis_error_when_removing_deltas(self, mock_get_redis, mock_logger):
        mock_redis = Mock()
        mock_pipeline = MagicMock()
        mock_pipeline.return_value.__enter__.return_value = mock_pipeline
        mock_pipeline.return_value.__exit__.return_value = None
        mock_pipeline.execute.side_effect = RedisError("Redis error")
        mock_redis.pipeline = mock_pipeline
        mock_get_redis.return_value = mock_redis
        article_ids = [111, 222, 333]

        _remove_synced_view_deltas_from_cache(mock_redis, article_ids)
        mock_logger.warning.assert_called_once_with(
            "Redis cleanup failed for article IDs %s: %s", article_ids, ANY
        )
        self.assertIsInstance(mock_logger.warning.call_args_list[0][0][2], RedisError)

    @override_settings(CACHES=CACHES)
    def test_failed_syncs_get_requeued(self):
        r = get_redis_connection("default")
        r.flushdb()

        r.sadd(VIEWED_ARTICLES_RETRY_SET_KEY, 9991, 9992)
        self.assertEqual(r.smembers(VIEWED_ARTICLES_RETRY_SET_KEY), {b"9991", b"9992"})
        self.assertEqual(r.smembers(VIEWED_ARTICLES_SET_KEY), set())

        with patch("articles.cache._decode_article_ids") as mock_decode:
            sync_article_views()
            mock_decode.assert_called_once_with([b"9991", b"9992"])

        self.assertEqual(r.smembers(VIEWED_ARTICLES_RETRY_SET_KEY), set())
        self.assertEqual(r.smembers(VIEWED_ARTICLES_SET_KEY), set())

        r.flushdb()

    @override_settings(CACHES=CACHES)
    @patch("articles.cache.bulk_increment_article_view_counts")
    def test_cached_views_get_reset(self, mock_increment):
        r = get_redis_connection("default")
        r.flushdb()

        key = ARTICLE_VIEWS_KEY.format(id=9991)
        r.set(key, 10)
        self.assertEqual(r.get(key), b"10")
        r.sadd(VIEWED_ARTICLES_SET_KEY, 9991)

        sync_article_views()
        mock_increment.assert_called_once_with({9991: 10})
        self.assertEqual(r.get(key), None)

        r.flushdb()

    @override_settings(CACHES=CACHES)
    @patch("articles.cache.logger.info")
    @patch("articles.cache.bulk_increment_article_view_counts")
    def test_single_batch(self, mock_increment, mock_info):
        r = get_redis_connection("default")
        r.flushdb()

        view_deltas = {9991: 3, 9992: 0, 9993: 10}
        keys = {id: ARTICLE_VIEWS_KEY.format(id=id) for id in view_deltas}

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            pipe.execute()

            [pipe.get(keys[article_id]) for article_id in view_deltas]
            view_counts = pipe.execute()
            self.assertFalse(any(vc is None for vc in view_counts))

            sync_article_views()
            expected_args = {k: v for k, v in view_deltas.items() if v > 0}
            mock_increment.assert_called_once_with(expected_args)

            viewed_articles = r.smembers(VIEWED_ARTICLES_SET_KEY)
            self.assertFalse(viewed_articles)

            [pipe.get(keys[article_id]) for article_id in view_deltas]
            view_counts = pipe.execute()
            self.assertTrue(all(vc is None for vc in view_counts))

        mock_info.assert_has_calls(
            [
                call("Synced views for %d articles in batch %s.", 2, 0),
                call("No articles to sync; exiting on batch %d.", 1),
            ]
        )

        r.flushdb()

    @override_settings(CACHES=CACHES)
    @patch("articles.cache.ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE", 2)
    @patch("articles.cache.logger.info")
    @patch("articles.cache.bulk_increment_article_view_counts")
    def test_multiple_batches(self, mock_increment, mock_info):
        r = get_redis_connection("default")
        r.flushdb()

        view_deltas = {9991: 3, 9992: 1, 9993: 0, 9994: 0, 9995: 10}
        keys = {id: ARTICLE_VIEWS_KEY.format(id=id) for id in view_deltas}

        with r.pipeline() as pipe:
            for article_id, delta in view_deltas.items():
                pipe.set(keys[article_id], delta)
                pipe.sadd(VIEWED_ARTICLES_SET_KEY, article_id)
            pipe.execute()

        with r.pipeline() as pipe:
            [pipe.get(keys[article_id]) for article_id in view_deltas]
            view_counts = pipe.execute()
        self.assertFalse(any(vc is None for vc in view_counts))

        self.assertEqual(
            r.smembers(VIEWED_ARTICLES_SET_KEY),
            {b"9991", b"9992", b"9993", b"9994", b"9995"},
        )

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

        with r.pipeline() as pipe:
            [pipe.get(keys[article_id]) for article_id in view_deltas]
            view_counts = pipe.execute()
        self.assertTrue(all(vc is None for vc in view_counts))

        self.assertCountEqual(
            mock_info.call_args_list,
            [
                call("Synced views for %d articles in batch %s.", 2, 0),
                call(
                    "No positive view deltas in batch %s for article IDs: %s",
                    1,
                    [9993, 9994],
                ),
                call("Synced views for %d articles in batch %s.", 1, 2),
                call("No articles to sync; exiting on batch %d.", 3),
            ],
        )

        r.flushdb()

    @patch("articles.cache._decode_article_ids")
    @patch("articles.cache._sync_article_batch")
    @patch("articles.cache.get_redis_connection")
    def test_max_iterations(self, mock_get_redis, mock_sync, mock_decode):
        mock_redis = Mock()
        article_ids = range(ARTICLE_VIEW_SYNC_MAX_ITERATIONS + 1)
        mock_redis.spop.return_value = True
        mock_get_redis.return_value = mock_redis
        mock_decode.side_effect = [
            [aid] * ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE for aid in article_ids
        ]

        with (patch("articles.cache._requeue_failed_view_syncs"),):
            sync_article_views()

        self.assertEqual(
            len(mock_sync.call_args_list), ARTICLE_VIEW_SYNC_MAX_ITERATIONS
        )
        for i, _call in enumerate(mock_sync.call_args_list):
            self.assertEqual(
                _call,
                call(
                    [article_ids[i]] * ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE, i, mock_redis
                ),
            )
        self.assertNotIn(
            call([article_ids[-1] * ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE], ANY, ANY),
            mock_sync.call_args_list,
        )
