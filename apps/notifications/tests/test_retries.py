import asyncio
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from notifications.services.retries import RetryPolicy, async_execute_with_retries


class TestAsyncExecuteWithRetries(SimpleTestCase):
    async def test_succeeds_without_retries(self) -> None:
        calls = {"n": 0}

        async def op():
            calls["n"] += 1
            return "ok"

        policy = RetryPolicy(max_retries=3, initial_backoff=0.01)

        result = await async_execute_with_retries(op, "op", policy)

        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 1)

    @patch("notifications.services.retries.random.uniform", return_value=0.0)
    @patch("notifications.services.retries.asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_transient_then_succeeds(
        self, mock_sleep: AsyncMock, mock_uniform
    ) -> None:
        calls = {"n": 0}

        async def op():
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("transient")
            return "ok"

        policy = RetryPolicy(
            max_retries=5,
            initial_backoff=0.01,
            transient_errors=(TimeoutError,),
        )

        result = await async_execute_with_retries(op, "op", policy)

        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(mock_sleep.await_count, 2)

    @patch("notifications.services.retries.random.uniform", return_value=0.0)
    @patch("notifications.services.retries.asyncio.sleep", new_callable=AsyncMock)
    async def test_transient_retries_exhausted_raises(
        self, mock_sleep: AsyncMock, mock_uniform
    ) -> None:
        calls = {"n": 0}

        async def op():
            calls["n"] += 1
            raise TimeoutError("transient")

        policy = RetryPolicy(
            max_retries=2,
            initial_backoff=0.01,
            transient_errors=(TimeoutError,),
        )

        with self.assertRaises(TimeoutError):
            await async_execute_with_retries(op, "op", policy)

        self.assertEqual(calls["n"], 3)
        self.assertEqual(mock_sleep.await_count, 2)

    @patch("notifications.services.retries.asyncio.sleep", new_callable=AsyncMock)
    async def test_permanent_error_not_retried(self, mock_sleep: AsyncMock) -> None:
        calls = {"n": 0}

        async def op():
            calls["n"] += 1
            raise ValueError("permanent")

        policy = RetryPolicy(
            max_retries=5,
            initial_backoff=0.01,
            permanent_errors=(ValueError,),
        )

        with self.assertRaises(ValueError):
            await async_execute_with_retries(op, "op", policy)

        self.assertEqual(calls["n"], 1)
        mock_sleep.assert_not_awaited()

    @patch("notifications.services.retries.asyncio.sleep", new_callable=AsyncMock)
    async def test_cancelled_error_is_propagated(self, mock_sleep: AsyncMock) -> None:
        calls = {"n": 0}

        async def op():
            calls["n"] += 1
            raise asyncio.CancelledError()

        policy = RetryPolicy(
            max_retries=5,
            initial_backoff=0.01,
            transient_errors=(TimeoutError,),
            permanent_errors=(ValueError,),
        )

        with self.assertRaises(asyncio.CancelledError):
            await async_execute_with_retries(op, "op", policy)

        self.assertEqual(calls["n"], 1)
        mock_sleep.assert_not_awaited()
