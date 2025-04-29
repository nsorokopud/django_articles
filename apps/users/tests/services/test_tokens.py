from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from users.models import TokenCounter, TokenType, User
from users.services.tokens import BaseTokenGenerator


class TestBaseTokenGenerator(TestCase):
    class TestTokenGenerator(BaseTokenGenerator):
        token_type = TokenType.ACCOUNT_ACTIVATION

    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.generator = self.TestTokenGenerator()

    def test_token_type_required_in_subclass(self):
        with self.assertRaises(ValueError):

            class InvalidTokenGenerator(BaseTokenGenerator):
                pass

    def test_token_type_must_be_instance_of_token_type(self):
        with self.assertRaises(ValueError):

            class InvalidTokenGenerator(BaseTokenGenerator):
                token_type = "invalid_token_type"

        class ValidTokenGenerator(BaseTokenGenerator):
            token_type = TokenType.ACCOUNT_ACTIVATION

    def test_increment_token_counter_called_when_making_token(self):
        with patch(
            "users.services.tokens.BaseTokenGenerator._increment_token_counter"
        ) as mock_increment:
            self.generator.make_token(self.user)
        mock_increment.assert_called_once_with(self.user)

    def test_get_token_count(self):
        self.assertEqual(self.generator.get_token_count(self.user), 0)

        TokenCounter.objects.create(
            user=self.user, token_type=self.generator.token_type, token_count=5
        )
        self.assertEqual(self.generator.get_token_count(self.user), 5)

    def test_hash_value_includes_token_count(self):
        timestamp = int(timezone.now().timestamp())
        user_login_timestamp = (
            ""
            if self.user.last_login is None
            else self.user.last_login.replace(microsecond=0, tzinfo=None)
        )
        expected_hash_value = (
            f"{self.user.pk}{self.user.password}{user_login_timestamp}"
            f"{timestamp}{self.user.email}0"
        )

        hash_value = self.generator._make_hash_value(self.user, timestamp)
        self.assertEqual(hash_value, expected_hash_value)

        TokenCounter.objects.create(
            user=self.user, token_type=self.generator.token_type, token_count=5
        )
        expected_hash_value = (
            f"{self.user.pk}{self.user.password}{user_login_timestamp}"
            f"{timestamp}{self.user.email}5"
        )
        hash_value = self.generator._make_hash_value(self.user, timestamp)
        self.assertEqual(hash_value, expected_hash_value)

    def test_increment_token_counter_with_preexisting_counter(self):
        self.assertEqual(TokenCounter.objects.count(), 0)

        self.generator._increment_token_counter(self.user)
        self.assertEqual(
            TokenCounter.objects.get(
                user=self.user, token_type=self.generator.token_type
            ).token_count,
            1,
        )

    def test_increment_token_counter_without_preexisting_counter(self):
        TokenCounter.objects.create(
            user=self.user, token_type=self.generator.token_type, token_count=10
        )
        self.generator._increment_token_counter(self.user)
        self.assertEqual(
            TokenCounter.objects.get(
                user=self.user, token_type=self.generator.token_type
            ).token_count,
            11,
        )
