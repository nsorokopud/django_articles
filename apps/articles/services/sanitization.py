# pylint: disable=E1101
from copy import deepcopy

import nh3


ALLOWED_TAGS = set(nh3.ALLOWED_TAGS) | {
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
}

ALLOWED_ATTRIBUTES = deepcopy(nh3.ALLOWED_ATTRIBUTES)

ALLOWED_ATTRIBUTES.setdefault("a", set()).update(
    {
        "href",
        "title",
        "target",
    }
)

ALLOWED_ATTRIBUTES.setdefault("img", set()).update(
    {
        "src",
        "alt",
        "title",
        "width",
        "height",
    }
)

ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_article_html(html: str) -> str:
    return nh3.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )
