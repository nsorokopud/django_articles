import logging
from urllib.parse import unquote

import pytz
from django.conf import settings
from django.utils import timezone


logger = logging.getLogger("uncatched_errors_logger")


class ErrorLoggingMiddleware:
    def __init__(self, get_response):
        self._get_response = get_response

    def __call__(self, request):
        return self._get_response(request)

    def process_exception(self, request, exception):
        logger.error(exception, exc_info=True)


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Attempts to activate a time zone from a cookie. Otherwise uses
        default time zone from settings
        """

        if getattr(settings, "USE_TZ", None):
            tz = request.COOKIES.get("timezone", None)
            if tz:
                tz = unquote(tz)  # cookie time zones are URI encoded

            try:
                timezone.activate(pytz.timezone(tz))
            except (pytz.UnknownTimeZoneError, AttributeError):
                timezone.activate(get_default_timezone())

        return self.get_response(request)


def get_default_timezone():
    if hasattr(settings, "DEFAULT_USER_TZ"):
        tz = settings.DEFAULT_USER_TZ
    elif hasattr(settings, "TIME_ZONE"):
        tz = settings.TIME_ZONE
    else:
        tz = "UTC"
    try:
        return pytz.timezone(tz)
    except (pytz.UnknownTimeZoneError, AttributeError):
        return pytz.utc
