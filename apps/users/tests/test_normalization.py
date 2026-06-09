from django.test import SimpleTestCase

from users.normalization import normalize_email, normalize_username


class TestNormalizeEmail(SimpleTestCase):
    def test_normalizes_email(self):
        self.assertEqual(normalize_email("  USER@TEST.COM  "), "user@test.com")

    def test_preserves_internal_whitespace(self):
        self.assertEqual(normalize_email("user name@test.com"), "user name@test.com")

    def test_returns_empty_string_for_none(self):
        self.assertEqual(normalize_email(None), "")

    def test_returns_empty_string_for_blank_string(self):
        self.assertEqual(normalize_email("   "), "")


class TestNormalizeUsername(SimpleTestCase):
    def test_normalizes_username(self):
        self.assertEqual(normalize_username("  MaxUser  "), "MaxUser")

    def test_preserves_case(self):
        self.assertEqual(normalize_username("MaxUser"), "MaxUser")

    def test_preserves_internal_whitespace(self):
        self.assertEqual(normalize_username("Max User"), "Max User")

    def test_returns_empty_string_for_none(self):
        self.assertEqual(normalize_username(None), "")

    def test_returns_empty_string_for_blank_string(self):
        self.assertEqual(normalize_username("   "), "")
