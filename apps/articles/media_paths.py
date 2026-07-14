from posixpath import normpath
from urllib.parse import unquote, urlparse

from django.conf import settings


_ARTICLE_MEDIA_STORAGE_ROOT = "articles/uploads"


def extract_article_media_storage_name_for_article(
    src: str | None, *, article_id: int | None, author_id: int | None
) -> str | None:
    storage_name = _extract_article_media_storage_name(src)

    if storage_name is None or article_id is None or author_id is None:
        return None

    article_prefix = f"{_ARTICLE_MEDIA_STORAGE_ROOT}/{author_id}/{article_id}/"
    return storage_name if storage_name.startswith(article_prefix) else None


def _extract_article_media_storage_name(src: str | None) -> str | None:
    src = (src or "").strip()
    if not src:
        return None

    try:
        parsed = urlparse(src)
    except ValueError:
        return None

    path = _normalize_untrusted_url_path(parsed.path)
    if path is None:
        return None

    if parsed.scheme or parsed.netloc:
        media_root = _find_allowed_media_root(parsed, path)
    else:
        media_root = _normalized_media_url_path()

    if media_root is None:
        return None

    media_prefix = f"{media_root.rstrip('/')}/"
    article_prefix = f"{media_prefix}{_ARTICLE_MEDIA_STORAGE_ROOT}/"

    if not path.startswith(article_prefix):
        return None

    return path[len(media_prefix) :]


def _normalized_media_url_path() -> str:
    path = urlparse(settings.MEDIA_URL).path or "/"
    return _normalize_url_path(path).rstrip("/") or "/"


def _find_allowed_media_root(parsed, path: str) -> str | None:
    if parsed.scheme != "https":
        return None

    origin = parsed.scheme, parsed.netloc

    for base_url in getattr(settings, "MEDIA_ALLOWED_ROOT_URLS", []):
        base = urlparse(base_url)

        if origin != (base.scheme, base.netloc):
            continue

        base_path = _normalize_url_path(base.path or "/").rstrip("/") or "/"

        if base_path == "/" or path == base_path or path.startswith(f"{base_path}/"):
            return base_path

    return None


def _normalize_untrusted_url_path(path: str) -> str | None:
    path = unquote(path or "")

    if "\x00" in path or "\\" in path or ".." in path.split("/"):
        return None

    return _normalize_url_path(path)


def _normalize_url_path(path: str) -> str:
    normalized = normpath(path or "/")
    return normalized if normalized.startswith("/") else f"/{normalized}"
