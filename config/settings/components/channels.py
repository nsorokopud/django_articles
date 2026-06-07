from .cache import REDIS_CHANNELS_URL


CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_CHANNELS_URL],
            "capacity": 50,  # max queued messages per channel
            "expiry": 10,  # seconds; drop queued messages after this
        },
    },
}
