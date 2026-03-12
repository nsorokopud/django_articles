import json
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase
from redis.exceptions import RedisError

from users.cache import (
    cache_subscribed_to_authors,
    get_cached_subscribed_to_authors,
    get_subscribed_to_authors_cache_key,
)


def sync_to_async_stub(func, thread_sensitive=False):
    async def _wrapped(*args, **kwargs):
        return func(*args, **kwargs)

    return _wrapped


class TestGetCachedSubscribedToAuthors(SimpleTestCase):
    def setUp(self) -> None:
        self.redis = MagicMock()
        self.user_id = 123

    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_cache_miss_returns_none(
        self, mock_get_redis, _mock_sync_to_async
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.get.return_value = None

        result = await get_cached_subscribed_to_authors(self.user_id)
        self.assertIsNone(result)
        self.redis.get.assert_called_once()

    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_decodes_bytes_and_parses(
        self, mock_get_redis, _mock_sync_to_async
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.get.return_value = b"[1,2,3]"

        result = await get_cached_subscribed_to_authors(self.user_id)
        self.assertEqual(result, [1, 2, 3])

    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_accepts_string(self, mock_get_redis, _mock_sync_to_async) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.get.return_value = "[4,5]"

        result = await get_cached_subscribed_to_authors(self.user_id)
        self.assertEqual(result, [4, 5])

    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_invalid_json_evicted_and_none(
        self, mock_get_redis, _mock_sync_to_async
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.get.return_value = b"not-json"
        self.redis.delete.return_value = 1

        result = await get_cached_subscribed_to_authors(self.user_id)
        self.assertIsNone(result)
        self.redis.delete.assert_called_once_with(
            get_subscribed_to_authors_cache_key(self.user_id)
        )

    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_non_list_payload_evicted_and_none(
        self, mock_get_redis, _mock_sync_to_async
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.get.return_value = b'{"a": 1}'
        self.redis.delete.return_value = 1

        result = await get_cached_subscribed_to_authors(self.user_id)
        self.assertIsNone(result)
        self.redis.delete.assert_called_once_with(
            get_subscribed_to_authors_cache_key(self.user_id)
        )

    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_non_int_items_evicted_and_none(
        self, mock_get_redis, _mock_sync_to_async
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.get.return_value = json.dumps(["x", "y"])
        self.redis.delete.return_value = 1

        result = await get_cached_subscribed_to_authors(self.user_id)
        self.assertIsNone(result)
        self.redis.delete.assert_called_once_with(
            get_subscribed_to_authors_cache_key(self.user_id)
        )

    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_redis_error_returns_none(
        self, mock_get_redis, _mock_sync_to_async
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.get.side_effect = RedisError("error")

        result = await get_cached_subscribed_to_authors(self.user_id)
        self.assertIsNone(result)


class TestCacheSubscribedToAuthors(SimpleTestCase):
    def setUp(self) -> None:
        self.redis = MagicMock()
        self.user_id = 123

    @patch("users.cache.randint", return_value=0)
    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_success_sets_value(
        self, mock_get_redis, _mock_sync_to_async, _mock_randint
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.setex.return_value = True

        ok = await cache_subscribed_to_authors(self.user_id, [10, 20, 30])
        self.assertTrue(ok)

        args, _ = self.redis.setex.call_args
        self.assertEqual(args[0], get_subscribed_to_authors_cache_key(self.user_id))
        self.assertEqual(args[1], settings.SUBSCRIBED_TO_AUTHORS_CACHE_TIMEOUT)
        self.assertEqual(args[2], "[10,20,30]")

    @patch("users.cache.randint", return_value=0)
    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_invalid_payload_returns_false(
        self, mock_get_redis, _mock_sync_to_async, _mock_randint
    ) -> None:
        mock_get_redis.return_value = self.redis

        ok = await cache_subscribed_to_authors(self.user_id, ["a"])
        self.assertFalse(ok)
        self.redis.setex.assert_not_called()

    @patch("users.cache.randint", return_value=0)
    @patch("users.cache.sync_to_async", side_effect=sync_to_async_stub)
    @patch("users.cache.get_redis_connection")
    async def test_redis_error_returns_false(
        self, mock_get_redis, _mock_sync_to_async, _mock_randint
    ) -> None:
        mock_get_redis.return_value = self.redis
        self.redis.setex.side_effect = RedisError("error")

        ok = await cache_subscribed_to_authors(self.user_id, [1, 2, 3])
        self.assertFalse(ok)
