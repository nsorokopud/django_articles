from html import unescape

from django.utils.html import strip_tags


def extract_searchable_text(html: str | None) -> str:
    text = unescape(strip_tags(html or ""))
    text = text.replace("\xa0", " ")
    return " ".join(text.split())
