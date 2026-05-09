# pylint: disable=E1101
from copy import deepcopy
from urllib.parse import urlparse

import nh3
from django.conf import settings

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

ALLOWED_ATTRIBUTES = deepcopy(nh3.ALLOWED_ATTRIBUTES)

ALLOWED_ATTRIBUTES.setdefault("a", set()).update({"href", "title", "target"})

ALLOWED_ATTRIBUTES["img"] = {"src", "alt", "title"}

for tag_name in ALIGNABLE_TAGS:
    ALLOWED_ATTRIBUTES.setdefault(tag_name, set()).add("style")


def sanitize_article_html(
    html: str, *, article_id: int | None, author_id: int | None
) -> str:
    def attribute_filter(tag: str, attr: str, value: str) -> str | None:
        return _article_attribute_filter(
            tag, attr, value, article_id=article_id, author_id=author_id
        )

    return nh3.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=getattr(settings, "ALLOWED_ARTICLE_CONTENT_URL_SCHEMES", {"https"}),
        link_rel="noopener noreferrer nofollow",
        attribute_filter=attribute_filter,
    )


def _article_attribute_filter(
    tag: str, attr: str, value: str, *, article_id: int | None, author_id: int | None
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

        return value if _is_allowed_anchor_href(value) else None

    if attr == "style" and tag in ALIGNABLE_TAGS:
        return _clean_alignment_style(value)

    return value


def _is_allowed_anchor_href(href: str) -> bool:
    parsed = urlparse((href or "").strip())

    # Allow site-relative/internal links like /articles/abc/
    if not parsed.scheme and not parsed.netloc:
        return True

    allowed_schemes = getattr(
        settings, "ALLOWED_ARTICLE_CONTENT_URL_SCHEMES", {"https"}
    )

    return parsed.scheme in allowed_schemes


def _filter_article_image_src(
    src: str, *, article_id: int | None, author_id: int | None
) -> str | None:
    file_name = extract_article_media_storage_name(src)

    if file_name and is_article_media_storage_name_for_article(
        file_name, article_id=article_id, author_id=author_id
    ):
        return src

    return None


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
