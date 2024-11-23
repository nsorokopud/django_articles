from unittest.mock import Mock, call, patch

import pytz

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from config.middleware import TimezoneMiddleware, get_default_timezone


class TimezoneMiddlewareTestCase(SimpleTestCase):
    def test_timezone_middleware(self):
        request = Mock()
        request.COOKIES = {"timezone": "America/Juneau"}
        request.path = reverse("articles")
        request.session = {}
        get_response = Mock()
        tz_middleware = TimezoneMiddleware(get_response)

        # USE_TZ=False
        with override_settings(USE_TZ=False), patch(
            "django.utils.timezone.activate"
        ) as timezone_activate__mock, patch(
            "config.middleware.get_default_timezone",
            return_value=pytz.timezone("America/Chihuahua"),
        ):
            response = tz_middleware(request)
            self.assertEqual(get_response.return_value, response)
            self.assertEqual(timezone_activate__mock.call_args_list, [])

        # USE_TZ=True, no timezone cookie
        request.COOKIES = {}
        with override_settings(USE_TZ=True), patch(
            "django.utils.timezone.activate"
        ) as timezone_activate__mock, patch(
            "config.middleware.get_default_timezone",
            return_value=pytz.timezone("America/Chihuahua"),
        ):
            response = tz_middleware(request)
            self.assertEqual(get_response.return_value, response)
            self.assertEqual(
                timezone_activate__mock.call_args_list, [call(pytz.timezone("America/Chihuahua"))]
            )

        # USE_TZ=True with valid timezone cookie
        request.COOKIES = {"timezone": "America/Juneau"}
        with override_settings(USE_TZ=True), patch(
            "django.utils.timezone.activate"
        ) as timezone_activate__mock, patch(
            "config.middleware.get_default_timezone",
            return_value=pytz.timezone("America/Chihuahua"),
        ):
            response = tz_middleware(request)
            self.assertEqual(get_response.return_value, response)
            self.assertEqual(
                timezone_activate__mock.call_args_list, [call(pytz.timezone("America/Juneau"))]
            )

        # USE_TZ=True with invalid timezone cookie
        request.COOKIES = {"timezone": "abc"}
        with override_settings(USE_TZ=True), patch(
            "django.utils.timezone.activate"
        ) as timezone_activate__mock, patch(
            "config.middleware.get_default_timezone",
            return_value=pytz.timezone("America/Chihuahua"),
        ):
            response = tz_middleware(request)
            self.assertEqual(get_response.return_value, response)
            self.assertEqual(
                timezone_activate__mock.call_args_list, [call(pytz.timezone("America/Chihuahua"))]
            )

    def test_get_default_timezone(self):
        with override_settings(DEFAULT_USER_TZ="Africa/Bamako"):
            res = get_default_timezone()
        self.assertEqual(res, pytz.timezone("Africa/Bamako"))

        with override_settings(DEFAULT_USER_TZ="Africa/Bamako", TIME_ZONE="America/Atka"):
            del settings.DEFAULT_USER_TZ
            res = get_default_timezone()
        self.assertEqual(res, pytz.timezone("America/Atka"))

        with override_settings(DEFAULT_USER_TZ="Africa/Bamako", TIME_ZONE="America/Atka"):
            del settings.DEFAULT_USER_TZ
            del settings.TIME_ZONE
            res = get_default_timezone()
        self.assertEqual(res, pytz.timezone("UTC"))

        with override_settings(DEFAULT_USER_TZ="abc"):
            res = get_default_timezone()
        self.assertEqual(res, pytz.timezone("UTC"))

        with patch("pytz.timezone", side_effect=AttributeError), override_settings(
            DEFAULT_USER_TZ="Africa/Bamako", TIME_ZONE="America/Atka"
        ):
            res = get_default_timezone()
        self.assertEqual(res, pytz.timezone("UTC"))
