from ..env import env


REDIS_HOST = env("REDIS_HOST", default="localhost")
REDIS_PORT = env.int("REDIS_PORT", default=6379)


def redis_url(*, db: int, host: str = REDIS_HOST, port: int = REDIS_PORT) -> str:
    return f"redis://{host}:{port}/{db}"


REDIS_CACHE_URL = env("REDIS_CACHE_URL", default=redis_url(db=0))
REDIS_SELECT2_URL = env("REDIS_SELECT2_URL", default=redis_url(db=1))
REDIS_CHANNELS_URL = env("REDIS_CHANNELS_URL", default=redis_url(db=2))
REDIS_CELERY_BROKER_URL = env("REDIS_CELERY_BROKER_URL", default=redis_url(db=3))
REDIS_CELERY_RESULT_URL = env("REDIS_CELERY_RESULT_URL", default=redis_url(db=4))

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
    "select2": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_SELECT2_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}


RATELIMIT_ENABLE = env.bool("RATELIMIT_ENABLE", default=True)
RATELIMIT_VIEW = "core.ratelimit.ratelimited"
