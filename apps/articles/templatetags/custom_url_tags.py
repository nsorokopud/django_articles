from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def relative_url(context, field_name, value) -> str:
    request = context.get("request")
    if request is None:
        return ""

    query_dict = request.GET.copy()

    if value in (None, "", []):
        query_dict.pop(field_name, None)
    elif isinstance(value, (list, tuple)):
        query_dict.setlist(field_name, value)
    else:
        query_dict[field_name] = value

    encoded = query_dict.urlencode()
    return f"?{encoded}" if encoded else ""
