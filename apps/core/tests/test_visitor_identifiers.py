from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from core.visitor_identifiers import (
    _hash_value,
    generate_fallback_visitor_id,
    get_visitor_id,
    get_visitor_ip,
)


User = get_user_model()


class TestVisitorIdentifiers(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _build_request(
        self,
        path="/test/",
        *,
        user=None,
        session_key=None,
        user_agent="TestUserAgent/1.0",
        accept_language="en-US",
    ):
        request = self.factory.get(
            path,
            HTTP_USER_AGENT=user_agent,
            HTTP_ACCEPT_LANGUAGE=accept_language,
        )

        if user is None:

            class AnonymousUserStub:
                is_authenticated = False

            request.user = AnonymousUserStub()
        else:
            request.user = user

        class SessionStub:
            def __init__(self, key):
                self.session_key = key

        request.session = SessionStub(session_key)
        return request

    def test_get_visitor_id_returns_user_id_for_authenticated_user(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        request = self._build_request(user=user, session_key="session-123")

        with patch("core.visitor_identifiers.get_visitor_ip") as mocked_get_ip:
            visitor_id = get_visitor_id(request)

        self.assertEqual(visitor_id, f"user:{user.id}")
        mocked_get_ip.assert_not_called()

    def test_get_visitor_id_returns_session_key_for_anonymous_user_with_session(self):
        request = self._build_request(session_key="session-abc")

        with patch("core.visitor_identifiers.get_visitor_ip") as mocked_get_ip:
            visitor_id = get_visitor_id(request)

        self.assertEqual(visitor_id, "session:session-abc")
        mocked_get_ip.assert_not_called()

    @override_settings(SECRET_KEY="test-secret-key")
    def test_get_visitor_id_returns_hashed_ip_when_no_user_and_no_session(self):
        request = self._build_request(session_key=None)

        with patch(
            "core.visitor_identifiers.get_visitor_ip",
            return_value="8.8.8.8",
        ) as mocked_get_ip:
            visitor_id = get_visitor_id(request)

        self.assertEqual(visitor_id, f"ip:{_hash_value('8.8.8.8')}")
        mocked_get_ip.assert_called_once_with(request)

    @override_settings(SECRET_KEY="test-secret-key")
    def test_get_visitor_id_falls_back_when_no_user_session_or_ip(self):
        request = self._build_request(
            session_key=None,
            user_agent="FallbackAgent/2.0",
            accept_language="en-GB",
        )

        with (
            patch(
                "core.visitor_identifiers.get_visitor_ip",
                return_value=None,
            ) as mocked_get_ip,
            patch(
                "core.visitor_identifiers.time.time",
                return_value=7200,
            ),
        ):
            visitor_id = get_visitor_id(request)

        self.assertTrue(visitor_id.startswith("fallback:"))
        mocked_get_ip.assert_called_once_with(request)

    @patch("core.visitor_identifiers.get_client_ip")
    def test_get_visitor_ip_returns_none_when_ip_is_missing(self, mocked_get_client_ip):
        mocked_get_client_ip.return_value = (None, False)
        request = self._build_request(path="/articles/test/")

        result = get_visitor_ip(request)

        self.assertIsNone(result)
        mocked_get_client_ip.assert_called_once_with(request)

    @patch("core.visitor_identifiers.get_client_ip")
    def test_get_visitor_ip_returns_none_for_invalid_ip(self, mocked_get_client_ip):
        mocked_get_client_ip.return_value = ("not-an-ip", True)
        request = self._build_request()

        result = get_visitor_ip(request)

        self.assertIsNone(result)

    @patch("core.visitor_identifiers.get_client_ip")
    @override_settings(ALLOW_NON_ROUTABLE_IPS=False)
    def test_get_visitor_ip_returns_none_for_non_routable_ip_when_disallowed(
        self, mocked_get_client_ip
    ):
        mocked_get_client_ip.return_value = ("192.168.1.10", False)
        request = self._build_request()

        result = get_visitor_ip(request)
        self.assertIsNone(result)

    @patch("core.visitor_identifiers.get_client_ip")
    @override_settings(ALLOW_NON_ROUTABLE_IPS=True)
    def test_get_visitor_ip_returns_non_routable_ip_when_allowed(
        self, mocked_get_client_ip
    ):
        mocked_get_client_ip.return_value = ("192.168.1.10", False)
        request = self._build_request()

        result = get_visitor_ip(request)
        self.assertEqual(result, "192.168.1.10")

    @patch("core.visitor_identifiers.get_client_ip")
    def test_get_visitor_ip_returns_valid_routable_ip(self, mocked_get_client_ip):
        mocked_get_client_ip.return_value = ("8.8.8.8", True)
        request = self._build_request()

        result = get_visitor_ip(request)

        self.assertEqual(result, "8.8.8.8")

    @override_settings(SECRET_KEY="test-secret-key")
    def test_generate_fallback_visitor_id_is_stable_within_same_time_window(self):
        request = self._build_request(
            user_agent="StableUA/1.0",
            accept_language="en-US",
        )

        with patch("core.visitor_identifiers.time.time", return_value=3599):
            visitor_id_1 = generate_fallback_visitor_id(request, time_window=3600)

        with patch("core.visitor_identifiers.time.time", return_value=3599):
            visitor_id_2 = generate_fallback_visitor_id(request, time_window=3600)

        self.assertEqual(visitor_id_1, visitor_id_2)
        self.assertTrue(visitor_id_1.startswith("fallback:"))

    @override_settings(SECRET_KEY="test-secret-key")
    def test_generate_fallback_visitor_id_changes_across_time_windows(self):
        request = self._build_request(
            user_agent="StableUA/1.0",
            accept_language="en-US",
        )

        with patch("core.visitor_identifiers.time.time", return_value=3599):
            visitor_id_1 = generate_fallback_visitor_id(request, time_window=3600)

        with patch("core.visitor_identifiers.time.time", return_value=3601):
            visitor_id_2 = generate_fallback_visitor_id(request, time_window=3600)

        self.assertNotEqual(visitor_id_1, visitor_id_2)

    @override_settings(SECRET_KEY="test-secret-key")
    def test_hash_value_is_stable_for_same_input(self):
        value = "8.8.8.8"

        hash_1 = _hash_value(value)
        hash_2 = _hash_value(value)

        self.assertEqual(hash_1, hash_2)

    @override_settings(SECRET_KEY="test-secret-key")
    def test_hash_value_changes_for_different_inputs(self):
        hash_1 = _hash_value("8.8.8.8")
        hash_2 = _hash_value("1.1.1.1")

        self.assertNotEqual(hash_1, hash_2)

    @override_settings(SECRET_KEY="secret-one")
    def test_hash_value_depends_on_secret_key(self):
        value = "8.8.8.8"

        hash_with_first_secret = _hash_value(value)

        with override_settings(SECRET_KEY="secret-two"):
            hash_with_second_secret = _hash_value(value)

        self.assertNotEqual(hash_with_first_secret, hash_with_second_secret)
