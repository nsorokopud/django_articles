from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from users.models import TokenCounter, TokenType, User
from users.services.tokens import BaseTokenGenerator


class TestBaseTokenGenerator(TestCase):
    class TestTokenGenerator(BaseTokenGenerator):
        token_type = TokenType.ACCOUNT_ACTIVATION

    class TestTokenGenerator2(BaseTokenGenerator):
        token_type = TokenType.EMAIL_CHANGE

    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.generator = self.TestTokenGenerator()
        self.generator2 = self.TestTokenGenerator2()

    def test_subclass_without_token_type(self):
        with self.assertRaises(ValueError):

            class InvalidTokenGenerator(BaseTokenGenerator):
                pass

    def test_subclass_with_invalid_token_type(self):
        with self.assertRaises(ValueError):

            class InvalidTokenGenerator(BaseTokenGenerator):
                token_type = "invalid_token_type"

        class ValidTokenGenerator(BaseTokenGenerator):
            token_type = TokenType.ACCOUNT_ACTIVATION

    def test_get_token_count(self):
        self.assertEqual(self.generator.get_token_count(self.user), 0)

        TokenCounter.objects.create(
            user=self.user, token_type=self.generator.token_type, token_count=5
        )
        self.assertEqual(self.generator.get_token_count(self.user), 5)

    def test_make_hash_value(self):
        timestamp = int(timezone.now().timestamp())
        user_login_timestamp = (
            ""
            if self.user.last_login is None
            else self.user.last_login.replace(microsecond=0, tzinfo=None)
        )
        expected_hash_value = (
            f"{self.user.pk}{self.user.password}{user_login_timestamp}"
            f"{timestamp}{self.user.email}{self.generator.token_type}0"
        )

        hash_value = self.generator._make_hash_value(self.user, timestamp)
        self.assertEqual(hash_value, expected_hash_value)

        counter = TokenCounter.objects.create(
            user=self.user, token_type=self.generator.token_type, token_count=5
        )
        expected_hash_value = (
            f"{self.user.pk}{self.user.password}{user_login_timestamp}"
            f"{timestamp}{self.user.email}{self.generator.token_type}5"
        )
        hash_value = self.generator._make_hash_value(self.user, timestamp)
        self.assertEqual(hash_value, expected_hash_value)

        counter.token_count += 1
        counter.save()
        expected_hash_value = (
            f"{self.user.pk}{self.user.password}{user_login_timestamp}"
            f"{timestamp}{self.user.email}{self.generator.token_type}6"
        )
        hash_value = self.generator._make_hash_value(self.user, timestamp)
        self.assertEqual(hash_value, expected_hash_value)

    def test_increment_token_counter(self):
        ttype = self.generator.token_type
        self.assertEqual(
            TokenCounter.objects.filter(user=self.user, token_type=ttype).count(), 0
        )
        self.generator._increment_token_counter(self.user)
        self.assertEqual(
            TokenCounter.objects.filter(user=self.user, token_type=ttype).count(),
            1,
        )
        self.generator._increment_token_counter(self.user)
        self.assertEqual(
            TokenCounter.objects.get(user=self.user, token_type=ttype).token_count,
            2,
        )

    def test_race_condition_during_token_creation_is_handled(self):
        TokenCounter.objects.create(
            user=self.user, token_type=self.generator.token_type, token_count=1
        )
        with patch("users.services.tokens.TokenCounter.objects.create") as mock_create:
            mock_create.side_effect = IntegrityError()
            self.generator.make_token(self.user)
        counter = TokenCounter.objects.get(
            user=self.user, token_type=self.generator.token_type
        )
        self.assertEqual(counter.token_count, 2)

    def test_token_valid_after_creation(self):
        token = self.generator.make_token(self.user)
        self.assertEqual(TokenCounter.objects.count(), 1)
        self.assertEqual(TokenCounter.objects.first().token_count, 1)
        self.assertTrue(self.generator.check_token(self.user, token))

    def test_token_invalid_after_making_new_token(self):
        token = self.generator.make_token(self.user)
        token2 = self.generator.make_token(self.user)
        self.assertFalse(self.generator.check_token(self.user, token))
        self.assertTrue(self.generator.check_token(self.user, token2))

    def test_different_type_token_invalid(self):
        token1 = self.generator.make_token(self.user)
        token2 = self.generator2.make_token(self.user)
        self.assertFalse(self.generator.check_token(self.user, token2))
        self.assertFalse(self.generator2.check_token(self.user, token1))

    def test_token_invalid_after_counter_increment(self):
        generator2 = self.TestTokenGenerator2()
        counter1 = TokenCounter.objects.create(
            user=self.user,
            token_type=TokenType.ACCOUNT_ACTIVATION,
            token_count=0,
        )
        counter2 = TokenCounter.objects.create(
            user=self.user,
            token_type=TokenType.EMAIL_CHANGE,
            token_count=0,
        )

        token1 = self.generator.make_token(self.user)
        token2 = generator2.make_token(self.user)

        self.assertTrue(self.generator.check_token(self.user, token1))
        self.assertTrue(generator2.check_token(self.user, token2))

        counter1.refresh_from_db()
        counter1.token_count += 1
        counter1.save()

        self.assertFalse(self.generator.check_token(self.user, token1))
        self.assertTrue(generator2.check_token(self.user, token2))

        counter2.refresh_from_db()
        counter2.token_count += 1
        counter2.save()
        self.assertFalse(self.generator.check_token(self.user, token1))
        self.assertFalse(generator2.check_token(self.user, token2))
