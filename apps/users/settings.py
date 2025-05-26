import os


SUBSCRIBERS_COUNT_CACHE_TIMEOUT = int(
    os.getenv("SUBSCRIBERS_COUNT_CACHE_TIMEOUT", "300")  # 5 minutes
)
