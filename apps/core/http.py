from django.core.exceptions import BadRequest


def get_int_param(request, name: str, default: int = 0) -> int:
    value = request.GET.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise BadRequest(f"invalid integer for '{name}'")
