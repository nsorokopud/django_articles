import os
import uuid
from typing import Any

from django.test import override_settings
from django.test.utils import TestContextDecorator


TEST_CACHE_ALIAS = "default"
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", default="redis://localhost:6379/15")
TEST_CACHE_KEY_PREFIX = os.getenv("TEST_CACHE_KEY_PREFIX", f"test:{uuid.uuid4().hex}")


def get_test_redis_caches() -> dict:
    return {
        TEST_CACHE_ALIAS: {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": TEST_REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": TEST_CACHE_KEY_PREFIX,
        },
        "select2": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": TEST_REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": f"{TEST_CACHE_KEY_PREFIX}:select2",
        },
    }


def override_settings_with_redis_cache(**extra_settings: Any) -> TestContextDecorator:
    return override_settings(CACHES=get_test_redis_caches(), **extra_settings)
