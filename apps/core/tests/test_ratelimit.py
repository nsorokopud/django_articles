import hashlib
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from core.ratelimit import (
    hash_value,
    post_email,
    ratelimited,
    user_or_ip,
)


User = get_user_model()


class TestRatelimit(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_hash_value_returns_sha256_hex_digest(self):
        value = "Test@Example.com"

        result = hash_value(value)

        self.assertEqual(result, hashlib.sha256(value.encode("utf-8")).hexdigest())

    def test_user_or_ip_returns_user_key_for_authenticated_user(self):
        user = User.objects.create_user(
            username="testuser", email="test@test.com", password="password123"
        )

        request = self.factory.get("/")
        request.user = user

        result = user_or_ip(None, request)

        self.assertEqual(result, f"user:{user.pk}")

    def test_user_or_ip_returns_remote_addr_key_for_anonymous_request(self):
        request = self.factory.get("/", REMOTE_ADDR="203.0.113.10")
        request.user = SimpleNamespace(is_authenticated=False)

        result = user_or_ip(None, request)

        self.assertEqual(result, "ip:203.0.113.10")

    def test_user_or_ip_prefers_first_forwarded_for_ip(self):
        request = self.factory.get(
            "/",
            REMOTE_ADDR="203.0.113.10",
            HTTP_X_FORWARDED_FOR="198.51.100.20, 198.51.100.21",
        )
        request.user = SimpleNamespace(is_authenticated=False)

        result = user_or_ip(None, request)

        self.assertEqual(result, "ip:198.51.100.20")

    def test_user_or_ip_handles_missing_user_attribute(self):
        request = self.factory.get("/", REMOTE_ADDR="203.0.113.10")

        result = user_or_ip(None, request)

        self.assertEqual(result, "ip:203.0.113.10")

    def test_post_email_uses_normalized_email_field(self):
        request = self.factory.post("/", data={"email": " Test@Test.COM "})
        request.user = SimpleNamespace(is_authenticated=False)

        result = post_email(None, request)

        expected_email = "test@test.com"
        self.assertEqual(result, f"email:{hash_value(expected_email)}")

    def test_post_email_uses_normalized_new_email_field(self):
        request = self.factory.post("/", data={"new_email": " New@Test.COM "})
        request.user = SimpleNamespace(is_authenticated=False)

        result = post_email(None, request)

        expected_email = "new@test.com"
        self.assertEqual(result, f"email:{hash_value(expected_email)}")

    def test_post_email_prefers_email_over_new_email(self):
        request = self.factory.post(
            "/",
            data={"email": " Primary@Test.COM ", "new_email": " Secondary@Test.COM "},
        )
        request.user = SimpleNamespace(is_authenticated=False)

        result = post_email(None, request)

        expected_email = "primary@test.com"
        self.assertEqual(result, f"email:{hash_value(expected_email)}")

    def test_post_email_falls_back_to_user_or_ip_without_email(self):
        request = self.factory.post("/", data={})
        request.user = SimpleNamespace(is_authenticated=False)
        request.META["REMOTE_ADDR"] = "203.0.113.10"

        result = post_email(None, request)

        self.assertEqual(result, "ip:203.0.113.10")

    def test_ratelimited_returns_429_response(self):
        request = self.factory.get("/")

        response = ratelimited(request, Exception("rate limited"))

        self.assertEqual(response.status_code, 429)
        self.assertContains(
            response, "Too many attempts. Please try again later.", status_code=429
        )

    def test_ratelimited_returns_json_for_ajax_request(self):
        request = self.factory.get("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        response = ratelimited(request, Exception("rate limited"))

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "message": "Too many attempts. Please try again later.",
            },
        )
