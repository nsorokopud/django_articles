# pylint: disable=E1101
from copy import deepcopy
from posixpath import normpath
from urllib.parse import unquote, urlparse

import nh3
from django.conf import settings


ALLOWED_TAGS = {
    "p",
    "br",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
    "code",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
}

ALIGNABLE_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "li",
    "td",
    "th",
}

ALLOWED_TEXT_ALIGN_VALUES = {"left", "center", "right", "justify"}

ALLOWED_ATTRIBUTES = deepcopy(nh3.ALLOWED_ATTRIBUTES)

ALLOWED_ATTRIBUTES.setdefault("a", set()).update({"href", "title", "target"})

ALLOWED_ATTRIBUTES.setdefault("img", set()).update(
    {"src", "alt", "title", "width", "height"}
)

for tag_name in ALIGNABLE_TAGS:
    ALLOWED_ATTRIBUTES.setdefault(tag_name, set()).add("style")


def sanitize_article_html(html: str) -> str:
    return nh3.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=getattr(settings, "ALLOWED_ARTICLE_CONTENT_URL_SCHEMES", {"https"}),
        link_rel="noopener noreferrer nofollow",
        attribute_filter=_attribute_filter,
    )


def _attribute_filter(tag: str, attr: str, value: str) -> str | None:
    if tag == "img" and attr == "src":
        return value if _is_allowed_image_src(value) else None

    if attr == "style" and tag in ALIGNABLE_TAGS:
        return _clean_alignment_style(value)

    return value


def _is_allowed_image_src(src: str) -> bool:
    src = (src or "").strip()
    if not src:
        return False

    parsed = urlparse(src)

    # Reject anything with scheme or host (http, https, //, data, blob, etc.)
    if parsed.scheme or parsed.netloc:
        return False

    return _is_allowed_local_media_src(src)


def _is_allowed_local_media_src(src: str) -> bool:
    parsed = urlparse(src)

    if parsed.scheme or parsed.netloc:
        return False

    path = unquote(parsed.path or "")

    # Reject null bytes and path traversal attempts (e.g. ../)
    if "\x00" in path or ".." in path.split("/"):
        return False

    normalized = normpath(path)

    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    media_path = urlparse(settings.MEDIA_URL).path.rstrip("/")
    allowed_prefix = f"{media_path}/articles/uploads/"

    return normalized.startswith(allowed_prefix)


def _clean_alignment_style(style: str) -> str | None:
    for declaration in (style or "").split(";"):
        name, sep, raw_value = declaration.partition(":")
        if not sep:
            continue

        if name.strip().lower() != "text-align":
            continue

        align = raw_value.strip().lower()
        if align in ALLOWED_TEXT_ALIGN_VALUES:
            return f"text-align: {align};"

    return None
