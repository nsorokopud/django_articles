from ..env import BASE_DIR, env


MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Allowed root URLs for media files (for validating external image URLs in TinyMCE)
MEDIA_ALLOWED_ROOT_URLS = env.list("MEDIA_ALLOWED_ROOT_URLS", default=[])

ALLOWED_IMAGE_UPLOAD_FILE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

MAX_IMAGE_UPLOAD_FILE_SIZE = env.int(
    "MAX_IMAGE_UPLOAD_FILE_SIZE", default=5 * 1024 * 1024  # 5MB default
)


STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
