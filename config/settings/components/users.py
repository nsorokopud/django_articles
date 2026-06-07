from datetime import timedelta

from ..env import env


USERS_SUBSCRIBERS_COUNT_CACHE_TIMEOUT_SECONDS = env.int(
    "USERS_SUBSCRIBERS_COUNT_CACHE_TIMEOUT_SECONDS", default=300  # 5 minutes
)

USERS_PENDING_EMAIL_CHANGE_TTL = timedelta(
    seconds=env.int(
        "USERS_PENDING_EMAIL_CHANGE_TTL_SECONDS", default=3600 * 2
    )  # 2 hours
)
