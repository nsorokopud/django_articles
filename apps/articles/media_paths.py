from pathlib import PurePosixPath
from posixpath import normpath
from urllib.parse import unquote, urlparse

from django.conf import settings


ARTICLE_MEDIA_STORAGE_ROOT = "articles/uploads"


def normalize_url_prefix(url: str | None) -> str | None:
    url = (url or "").strip()

    if not url:
        return None

    return url if url.endswith("/") else f"{url}/"


def extract_article_media_storage_name(src: str | None) -> str | None:
    if not src:
        return None

    parsed = urlparse(src.strip())
    is_absolute = bool(parsed.scheme or parsed.netloc)

    if is_absolute:
        media_url_path = _get_allowed_media_root_path(parsed)
        if media_url_path is None:
            return None
    else:
        media_url_path = urlparse(settings.MEDIA_URL).path or "/"

    path = unquote(parsed.path or "")

    if _has_unsafe_path_segments(path):
        return None

    normalized_path = _normalize_url_path(path)
    media_url_path = _normalize_url_path(media_url_path).rstrip("/") or "/"

    storage_name = _strip_media_url_prefix(
        normalized_path=normalized_path, media_url_path=media_url_path
    )

    if storage_name is None:
        return None

    if not storage_name.startswith(f"{ARTICLE_MEDIA_STORAGE_ROOT}/"):
        return None

    return storage_name


def is_article_media_storage_name_for_article(
    storage_name: str, *, article_id: int | None, author_id: int | None
) -> bool:
    allowed_prefix = _get_article_media_storage_prefix(
        article_id=article_id, author_id=author_id
    )

    return bool(allowed_prefix and storage_name.startswith(allowed_prefix))


def _get_allowed_media_root_path(parsed) -> str | None:
    if parsed.scheme != "https":
        return None

    path = unquote(parsed.path or "")

    if _has_unsafe_path_segments(path):
        return None

    normalized_path = _normalize_url_path(path)

    for base_url in getattr(settings, "MEDIA_ALLOWED_ROOT_URLS", []):
        base = urlparse(base_url)

        if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
            continue

        base_path = _normalize_url_path(base.path or "/").rstrip("/") or "/"

        if (
            base_path == "/"
            or normalized_path == base_path
            or normalized_path.startswith(f"{base_path}/")
        ):
            return base_path

    return None


def _strip_media_url_prefix(*, normalized_path: str, media_url_path: str) -> str | None:
    prefix = f"{media_url_path.rstrip('/')}/"

    if not normalized_path.startswith(prefix):
        return None

    return normalized_path.removeprefix(prefix).lstrip("/")


def _get_article_media_storage_prefix(
    *, article_id: int | None, author_id: int | None
) -> str | None:
    if article_id is None or author_id is None:
        return None

    return f"{ARTICLE_MEDIA_STORAGE_ROOT}/{author_id}/{article_id}/"


def _normalize_url_path(path: str) -> str:
    normalized = normpath(path or "/")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _has_unsafe_path_segments(path: str) -> bool:
    """Detect null bytes and directory traversal attempts."""
    return "\x00" in path or ".." in PurePosixPath(path).parts
