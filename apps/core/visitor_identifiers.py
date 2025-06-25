import hashlib
import ipaddress
import logging
import time
from typing import Optional

from django.http import HttpRequest
from ipware import get_client_ip

from config.settings import ALLOW_NON_ROUTABLE_IPS


logger = logging.getLogger("default_logger")


def get_visitor_id(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.id}"

    if request.session.session_key:
        return f"session:{request.session.session_key}"

    ip = get_visitor_ip(request)
    if ip:
        hashed_ip = hashlib.sha256(ip.encode()).hexdigest()
        return f"ip:{hashed_ip}"

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

    if not is_routable and not ALLOW_NON_ROUTABLE_IPS:
        logger.info(
            "Non-routable IP address (%s) detected for request %s", ip, request.path
        )
        return None

    return ip


def generate_fallback_visitor_id(request: HttpRequest, time_window: int = 3600) -> str:
    """Generates a stable fallback identifier based on user agent and
    time windows for anonymous users without a valid IP or session.

    Should be used as a last-resort mechanism when the user's IP cannot
    be determined and no session key exists.

    time_window: a time-based window in seconds (1 hour by default)
    during which the same browser will get the same id generated.
    """
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    time_bucket = int(time.time() // time_window)
    raw_id_source = f"{user_agent}:{time_bucket}"
    # hashing used to make ids consistent and compact
    id_hash = hashlib.sha256(raw_id_source.encode()).hexdigest()
    return f"fallback:{id_hash}"
