from datetime import timedelta

from ..env import env


USERS_PENDING_EMAIL_CHANGE_TTL = timedelta(
    seconds=env.int(
        "USERS_PENDING_EMAIL_CHANGE_TTL_SECONDS", default=3600 * 2
    )  # 2 hours
)
