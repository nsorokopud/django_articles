import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Sequence, TypeVar


T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int
    initial_backoff: float
    backoff_factor: float = 2
    timeout_seconds: Optional[float] = None
    transient_errors: Sequence[type[BaseException]] = ()
    permanent_errors: Sequence[type[BaseException]] = ()

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.initial_backoff <= 0:
            raise ValueError("initial_backoff must be > 0")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor must be >= 1")


async def async_execute_with_retries(
    operation: Callable[[], Awaitable[T]],
    operation_name: str,
    policy: RetryPolicy,
    extra_context: Optional[dict[str, Any]] = None,
) -> T:
    """Execute an async operation with retries.

    Retries use exponential backoff with full jitter.
    Exceptions in `permanent_errors` fail immediately,
    while other unexpected exceptions are logged and re-raised.
    """
    context_str = _format_log_context(extra_context)
    total_attempts = 1 + policy.max_retries
    permanent_errors = tuple(policy.permanent_errors)
    transient_errors = tuple(policy.transient_errors)

    for attempt in range(1, total_attempts + 1):
        try:
            if policy.timeout_seconds is not None:
                async with asyncio.timeout(policy.timeout_seconds):
                    return await operation()
            return await operation()

        except asyncio.CancelledError:  # pylint: disable=W0706
            raise
        except permanent_errors as e:  # pylint: disable=E0712
            logger.error(
                "%s non-retriable error%s: %s.", operation_name, context_str, e
            )
            raise
        except transient_errors as e:  # pylint: disable=E0712
            if attempt < total_attempts:
                nominal_delay = policy.initial_backoff * policy.backoff_factor ** (
                    attempt - 1
                )
                delay = random.uniform(0, nominal_delay)  # nosec B311
                logger.debug(
                    "%s transient error (attempt %d/%d)%s: %s. Will retry in %.2fs.",
                    operation_name,
                    attempt,
                    total_attempts,
                    context_str,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            logger.error("%s retries exhausted%s: %s.", operation_name, context_str, e)
            raise
        except Exception:
            logger.exception("%s unexpected error%s.", operation_name, context_str)
            raise
    raise AssertionError("unreachable")


def _format_log_context(context: Optional[dict[str, Any]]) -> str:
    if not context:
        return ""
    return " (" + "; ".join(f"{k}:{v}" for k, v in context.items()) + ")"
