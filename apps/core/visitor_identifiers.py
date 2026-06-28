import hashlib
import ipaddress
import logging
import time
from typing import Optional

from django.conf import settings
from django.http import HttpRequest
from ipware import get_client_ip


logger = logging.getLogger(__name__)


def get_visitor_id(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.id}"

    session_key = request.session.session_key
    if session_key:
        return f"session:{session_key}"

    ip = get_visitor_ip(request)
    if ip:
        return f"ip:{_hash_value(ip)}"

    return generate_fallback_visitor_id(request)


def get_visitor_ip(request: HttpRequest) -> Optional[str]:
    ip, is_routable = get_client_ip(request)

    if ip is None:
        logger.warning(
            "Could not determine client IP address for request: %s", request.path
        )
        return None

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        logger.warning("Invalid IP address detected: %s", ip)
        return None

    if not is_routable and not settings.ALLOW_NON_ROUTABLE_IPS:
        logger.info(
            "Non-routable IP address (%s) detected for request %s", ip, request.path
        )
        return None

    return ip


def generate_fallback_visitor_id(request: HttpRequest, time_window: int = 3600) -> str:
    """Last-resort identifier for anonymous users without session or IP.

    This is intentionally approximate and should be used only when
    stronger identifiers are unavailable.
    """
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    accept_language = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    time_bucket = int(time.time() // time_window)
    raw_id_source = f"{user_agent}:{accept_language}:{time_bucket}"
    return f"fallback:{_hash_value(raw_id_source)}"


def _hash_value(value: str) -> str:
    salted = f"{settings.SECRET_KEY}:{value}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()
