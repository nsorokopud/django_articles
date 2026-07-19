# pylint: disable=E1101
from urllib.parse import urlparse

import nh3
from django.conf import settings

from ..media_paths import extract_article_media_storage_name_for_article


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
    **{tag: {"style"} for tag in ALIGNABLE_TAGS},
}


def sanitize_article_html(
    html: str, *, article_id: int | None, author_id: int | None
) -> str:
    def attribute_filter(tag: str, attr: str, value: str) -> str | None:
        match tag, attr:
            case "img", "src":
                storage_name = extract_article_media_storage_name_for_article(
                    value, article_id=article_id, author_id=author_id
                )
                return value if storage_name else None

            case "a", "href":
                return _filter_anchor_href(value)

            case "a", "target":
                target = value.strip().lower()
                return target if target in {"_blank", "_self"} else None

            case _, "style":
                return _clean_alignment_style(value)

            case _:
                return value

    return nh3.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=getattr(
            settings,
            "ARTICLES_ALLOWED_ARTICLE_CONTENT_URL_SCHEMES",
            {"https"},
        ),
        link_rel="noopener noreferrer nofollow",
        attribute_filter=attribute_filter,
    )


def _filter_anchor_href(value: str) -> str | None:
    href = (value or "").strip()

    if not href or _contains_control_char(href):
        return None

    try:
        parsed = urlparse(href)

        if (
            not parsed.scheme
            or parsed.username
            or parsed.password
            or (parsed.scheme.lower() in {"http", "https"} and not parsed.hostname)
        ):
            return None
    except ValueError:
        return None

    return href


def _clean_alignment_style(style: str) -> str | None:
    for declaration in (style or "").split(";"):
        name, separator, value = declaration.partition(":")

        if separator and name.strip().lower() == "text-align":
            align = value.strip().lower()

            if align in ALLOWED_TEXT_ALIGN_VALUES:
                return f"text-align: {align};"

    return None


def _contains_control_char(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)
