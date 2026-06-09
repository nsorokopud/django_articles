import hashlib

from django.http import HttpResponse

from .views import Error429View


def ratelimited(request, _exception) -> HttpResponse:
    return Error429View.as_view()(request)


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def user_or_ip(_group, request) -> str:
    user = getattr(request, "user", None)

    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")

    return f"ip:{ip}"


def post_email(group, request) -> str:
    from users.normalization import normalize_email

    email = normalize_email(request.POST.get("email")) or normalize_email(
        request.POST.get("new_email")
    )
    if not email:
        return user_or_ip(group, request)

    return f"email:{hash_value(email)}"
