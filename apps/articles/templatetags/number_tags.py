from babel.numbers import format_compact_decimal
from django import template


register = template.Library()


@register.filter
def compact_count(value) -> str:
    """Format a count using compact notation."""
    if value is None:
        return ""

    try:
        count = int(value)
    except (TypeError, ValueError, OverflowError):
        return str(value)

    return format_compact_decimal(count, locale="en_US", fraction_digits=1)
