# pylint: disable=E1101
from collections.abc import Container
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlparse

import nh3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ..constants import ALLOWED_ARTICLE_INTERNAL_LINK_PREFIXES
from ..media_paths import (
    extract_article_media_storage_name,
    is_article_media_storage_name_for_article,
)


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

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title"},
}

for tag_name in ALIGNABLE_TAGS:
    ALLOWED_ATTRIBUTES.setdefault(tag_name, set()).add("style")


def sanitize_article_html(
    html: str, *, article_id: int | None, author_id: int | None
) -> str:
    allowed_internal_link_hosts = _get_validated_internal_article_link_hosts()
    allowed_internal_link_prefixes = _get_validated_internal_article_link_prefixes()

    def attribute_filter(tag: str, attr: str, value: str) -> str | None:
        return _article_attribute_filter(
            tag,
            attr,
            value,
            article_id=article_id,
            author_id=author_id,
            allowed_internal_link_hosts=allowed_internal_link_hosts,
            allowed_internal_link_prefixes=allowed_internal_link_prefixes,
        )

    return nh3.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=getattr(
            settings, "ARTICLES_ALLOWED_ARTICLE_CONTENT_URL_SCHEMES", {"https"}
        ),
        link_rel="noopener noreferrer nofollow",
        attribute_filter=attribute_filter,
    )


def _article_attribute_filter(  # pylint: disable=too-many-return-statements
    tag: str,
    attr: str,
    value: str,
    *,
    article_id: int | None,
    author_id: int | None,
    allowed_internal_link_hosts: Container[str],
    allowed_internal_link_prefixes: Iterable[str],
) -> str | None:
    tag = tag.lower()
    attr = attr.lower()

    if attr == "src":
        if tag != "img":
            return None
        return _filter_article_image_src(
            value, article_id=article_id, author_id=author_id
        )

    if attr == "href":
        if tag != "a":
            return None
        return (
            value
            if _is_allowed_anchor_href(
                value,
                allowed_internal_link_hosts=allowed_internal_link_hosts,
                allowed_internal_link_prefixes=allowed_internal_link_prefixes,
            )
            else None
        )

    if attr == "target" and tag == "a":
        target = (value or "").strip().lower()
        return target if target in {"_blank", "_self"} else None

    if attr == "style" and tag in ALIGNABLE_TAGS:
        return _clean_alignment_style(value)

    return value


def _filter_article_image_src(
    src: str, *, article_id: int | None, author_id: int | None
) -> str | None:
    file_name = extract_article_media_storage_name(src)

    if file_name and is_article_media_storage_name_for_article(
        file_name, article_id=article_id, author_id=author_id
    ):
        return src

    return None


def _is_allowed_anchor_href(  # pylint: disable=too-many-return-statements
    href: str,
    *,
    allowed_internal_link_hosts: Container[str],
    allowed_internal_link_prefixes: Iterable[str],
) -> bool:
    href = (href or "").strip()

    # Disallow empty hrefs and hrefs with control characters like "\n"
    if not href or _contains_control_char(href):
        return False

    parsed = urlparse(href)

    # Disallow protocol-relative URLs like //evil.example.com
    if not parsed.scheme and parsed.netloc:
        return False

    # Relative/internal URL: /articles/...
    if not parsed.scheme and not parsed.netloc:
        if not parsed.path:
            return False

        return _is_allowed_internal_article_link(
            parsed.path, allowed_prefixes=allowed_internal_link_prefixes
        )

    if parsed.username or parsed.password:
        return False

    allowed_schemes = {
        scheme.lower()
        for scheme in getattr(
            settings, "ARTICLES_ALLOWED_ARTICLE_CONTENT_URL_SCHEMES", {"https"}
        )
    }

    if parsed.scheme.lower() not in allowed_schemes:
        return False

    host = parsed.hostname.lower() if parsed.hostname else ""

    if host in allowed_internal_link_hosts:
        return _is_allowed_internal_article_link(
            parsed.path, allowed_prefixes=allowed_internal_link_prefixes
        )

    return True


def _is_allowed_internal_article_link(
    path: str, *, allowed_prefixes: Iterable[str]
) -> bool:
    if not path.startswith("/"):
        return False

    decoded_path = unquote(path)

    if (
        _contains_control_char(decoded_path)
        or ".." in PurePosixPath(decoded_path).parts
    ):
        return False

    return any(decoded_path.startswith(prefix) for prefix in allowed_prefixes)


@lru_cache(maxsize=1)
def _get_validated_internal_article_link_hosts() -> frozenset[str]:
    configured_hosts = getattr(
        settings, "ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS", ()
    )

    hosts = []
    for host in configured_hosts:
        if not isinstance(host, str):
            raise ImproperlyConfigured(
                "ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS must contain host strings"
            )

        normalized = host.strip().lower()

        if (
            not normalized
            or "/" in normalized
            or "\\" in normalized
            or ":" in normalized
        ):
            raise ImproperlyConfigured(
                "ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS must contain "
                "bare hostnames only"
            )

        hosts.append(normalized)

    return frozenset(hosts)


@lru_cache(maxsize=1)
def _get_validated_internal_article_link_prefixes() -> frozenset[str]:
    prefixes = tuple(ALLOWED_ARTICLE_INTERNAL_LINK_PREFIXES)

    for prefix in prefixes:
        if not _is_valid_internal_link_prefix(prefix):
            raise ImproperlyConfigured(
                "ALLOWED_ARTICLE_INTERNAL_LINK_PREFIXES must contain only unencoded "
                "absolute path prefixes that start and end with '/', are not '/', "
                "and do not contain null bytes or '..' path segments"
            )

    return frozenset(prefixes)


def _is_valid_internal_link_prefix(prefix: object) -> bool:
    if not isinstance(prefix, str):
        return False

    decoded_prefix = unquote(prefix)

    return (
        decoded_prefix.startswith("/")
        and decoded_prefix.endswith("/")
        and decoded_prefix != "/"
        and "\x00" not in decoded_prefix
        and ".." not in PurePosixPath(decoded_prefix).parts
        and decoded_prefix == prefix
    )


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


def _contains_control_char(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)
