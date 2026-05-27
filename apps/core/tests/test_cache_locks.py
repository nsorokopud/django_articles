from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django_redis import get_redis_connection
from django_redis.exceptions import ConnectionInterrupted
from redis.exceptions import RedisError

from core.cache_locks import RELEASE_LOCK_LUA, cache_lock, release_redis_lock


TEST_CACHE_ALIAS = "default"


class TestCacheLock(SimpleTestCase):
    @patch("core.cache_locks.release_redis_lock")
    @patch("core.cache_locks.get_redis_connection")
    def test_yields_acquired_lock_when_redis_set_succeeds(
        self, mock_get_redis_connection, mock_release_redis_lock
    ):
        redis_conn = Mock()
        redis_conn.set.return_value = True
        mock_get_redis_connection.return_value = redis_conn

        with cache_lock(
            lock_key="test-lock", lock_value="test-value", timeout=60
        ) as lock:
            self.assertTrue(lock.acquired)
            self.assertEqual(lock.lock_key, "test-lock")
            self.assertEqual(lock.lock_value, "test-value")

        mock_get_redis_connection.assert_called_once_with("default")
        redis_conn.set.assert_called_once_with(
            "test-lock", "test-value", nx=True, ex=60
        )
        mock_release_redis_lock.assert_called_once_with(
            lock_key="test-lock", lock_value="test-value", cache_alias="default"
        )

    @patch("core.cache_locks.release_redis_lock")
    @patch("core.cache_locks.get_redis_connection")
    def test_yields_not_acquired_lock_when_redis_set_fails(
        self, mock_get_redis_connection, mock_release_redis_lock
    ):
        redis_conn = Mock()
        redis_conn.set.return_value = None
        mock_get_redis_connection.return_value = redis_conn

        with cache_lock(
            lock_key="test-lock", lock_value="test-value", timeout=60
        ) as lock:
            self.assertFalse(lock.acquired)
            self.assertEqual(lock.lock_key, "test-lock")
            self.assertEqual(lock.lock_value, "test-value")

        redis_conn.set.assert_called_once_with(
            "test-lock", "test-value", nx=True, ex=60
        )
        mock_release_redis_lock.assert_not_called()

    @patch("core.cache_locks.release_redis_lock")
    @patch("core.cache_locks.get_redis_connection")
    def test_releases_acquired_lock_when_body_raises(
        self, mock_get_redis_connection, mock_release_redis_lock
    ):
        redis_conn = Mock()
        redis_conn.set.return_value = True
        mock_get_redis_connection.return_value = redis_conn

        with self.assertRaises(RuntimeError):
            with cache_lock(lock_key="test-lock", lock_value="test-value", timeout=60):
                raise RuntimeError("boom")

        mock_release_redis_lock.assert_called_once_with(
            lock_key="test-lock", lock_value="test-value", cache_alias="default"
        )

    @patch("core.cache_locks.release_redis_lock")
    @patch("core.cache_locks.get_redis_connection")
    def test_does_not_release_unacquired_lock_when_body_raises(
        self, mock_get_redis_connection, mock_release_redis_lock
    ):
        redis_conn = Mock()
        redis_conn.set.return_value = None
        mock_get_redis_connection.return_value = redis_conn

        with self.assertRaises(RuntimeError):
            with cache_lock(lock_key="test-lock", lock_value="test-value", timeout=60):
                raise RuntimeError("boom")

        mock_release_redis_lock.assert_not_called()

    @patch("core.cache_locks.release_redis_lock")
    @patch("core.cache_locks.get_redis_connection")
    @patch("core.cache_locks.uuid4")
    def test_generates_lock_value_when_not_provided(
        self, mock_uuid4, mock_get_redis_connection, mock_release_redis_lock
    ):
        mock_uuid4.return_value.hex = "generated-value"

        redis_conn = Mock()
        redis_conn.set.return_value = True
        mock_get_redis_connection.return_value = redis_conn

        with cache_lock(lock_key="test-lock", timeout=60) as lock:
            self.assertTrue(lock.acquired)
            self.assertEqual(lock.lock_value, "generated-value")

        redis_conn.set.assert_called_once_with(
            "test-lock", "generated-value", nx=True, ex=60
        )
        mock_release_redis_lock.assert_called_once_with(
            lock_key="test-lock", lock_value="generated-value", cache_alias="default"
        )

    @patch("core.cache_locks.release_redis_lock")
    @patch("core.cache_locks.get_redis_connection")
    def test_uses_custom_cache_alias(
        self, mock_get_redis_connection, mock_release_redis_lock
    ):
        redis_conn = Mock()
        redis_conn.set.return_value = True
        mock_get_redis_connection.return_value = redis_conn

        with cache_lock(
            lock_key="test-lock",
            lock_value="test-value",
            timeout=60,
            cache_alias="locks",
        ):
            pass

        mock_get_redis_connection.assert_called_once_with("locks")
        redis_conn.set.assert_called_once_with(
            "test-lock", "test-value", nx=True, ex=60
        )
        mock_release_redis_lock.assert_called_once_with(
            lock_key="test-lock", lock_value="test-value", cache_alias="locks"
        )

    def test_raises_for_zero_timeout(self):
        with self.assertRaisesMessage(ValueError, "timeout must be > 0"):
            with cache_lock(lock_key="test-lock", timeout=0):
                pass

    def test_raises_for_negative_timeout(self):
        with self.assertRaisesMessage(ValueError, "timeout must be > 0"):
            with cache_lock(lock_key="test-lock", timeout=-1):
                pass


class TestReleaseRedisLock(SimpleTestCase):
    @patch("core.cache_locks.get_redis_connection")
    def test_releases_lock_with_lua_compare_and_delete(self, mock_get_redis_connection):
        redis_conn = Mock()
        mock_get_redis_connection.return_value = redis_conn

        release_redis_lock(lock_key="test-lock", lock_value="test-value")

        mock_get_redis_connection.assert_called_once_with("default")
        redis_conn.eval.assert_called_once_with(
            RELEASE_LOCK_LUA, 1, "test-lock", "test-value"
        )

    @patch("core.cache_locks.get_redis_connection")
    def test_uses_custom_cache_alias(self, mock_get_redis_connection):
        redis_conn = Mock()
        mock_get_redis_connection.return_value = redis_conn

        release_redis_lock(
            lock_key="test-lock", lock_value="test-value", cache_alias="locks"
        )

        mock_get_redis_connection.assert_called_once_with("locks")
        redis_conn.eval.assert_called_once_with(
            RELEASE_LOCK_LUA, 1, "test-lock", "test-value"
        )

    @patch("core.cache_locks.logger.exception")
    @patch("core.cache_locks.get_redis_connection")
    def test_logs_redis_error(self, mock_get_redis_connection, mock_logger_exception):
        redis_conn = Mock()
        redis_conn.eval.side_effect = RedisError("redis down")
        mock_get_redis_connection.return_value = redis_conn

        release_redis_lock(lock_key="test-lock", lock_value="test-value")

        mock_logger_exception.assert_called_once_with(
            "Failed to release lock %s.", "test-lock"
        )

    @patch("core.cache_locks.logger.exception")
    @patch("core.cache_locks.get_redis_connection")
    def test_logs_connection_interrupted(
        self, mock_get_redis_connection, mock_logger_exception
    ):
        redis_conn = Mock()
        redis_conn.eval.side_effect = ConnectionInterrupted("redis interrupted")
        mock_get_redis_connection.return_value = redis_conn

        release_redis_lock(lock_key="test-lock", lock_value="test-value")

        mock_logger_exception.assert_called_once_with(
            "Failed to release lock %s.", "test-lock"
        )


@override_settings(CACHES=settings.TEST_REDIS_CACHES)
class TestCacheLockRedisIntegration(TestCase):
    def setUp(self):
        self.redis = get_redis_connection(TEST_CACHE_ALIAS)
        self.lock_key = "test:core-cache-locks:integration-lock"
        self.redis.delete(self.lock_key)

    def tearDown(self):
        self.redis.delete(self.lock_key)

    def test_cache_lock_acquires_and_releases_real_redis_lock(self):
        with cache_lock(
            lock_key=self.lock_key,
            lock_value="owner-1",
            timeout=60,
            cache_alias=TEST_CACHE_ALIAS,
        ) as lock:
            self.assertTrue(lock.acquired)
            self.assertEqual(self.redis.get(self.lock_key), b"owner-1")

        self.assertIsNone(self.redis.get(self.lock_key))

    def test_cache_lock_does_not_acquire_when_lock_already_exists(self):
        self.redis.set(self.lock_key, "owner-1", ex=60)

        with cache_lock(
            lock_key=self.lock_key,
            lock_value="owner-2",
            timeout=60,
            cache_alias=TEST_CACHE_ALIAS,
        ) as lock:
            self.assertFalse(lock.acquired)
            self.assertEqual(self.redis.get(self.lock_key), b"owner-1")

        self.assertEqual(self.redis.get(self.lock_key), b"owner-1")

    def test_release_redis_lock_does_not_delete_lock_with_different_value(self):
        self.redis.set(self.lock_key, "owner-1", ex=60)

        release_redis_lock(
            lock_key=self.lock_key, lock_value="owner-2", cache_alias=TEST_CACHE_ALIAS
        )

        self.assertEqual(self.redis.get(self.lock_key), b"owner-1")

    def test_release_redis_lock_deletes_lock_with_matching_value(self):
        self.redis.set(self.lock_key, "owner-1", ex=60)

        release_redis_lock(
            lock_key=self.lock_key, lock_value="owner-1", cache_alias=TEST_CACHE_ALIAS
        )

        self.assertIsNone(self.redis.get(self.lock_key))
