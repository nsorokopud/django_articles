from django.test import TestCase
from django.utils import timezone

from users.models import PendingEmailChange, TokenCounter, TokenType, User
from users.services.tokens import (
    AccountActivationTokenGenerator,
    BaseTokenGenerator,
    EmailChangeTokenGenerator,
    activation_token_generator,
    email_change_token_generator,
    password_reset_token_generator,
)


class TestBaseTokenGenerator(TestCase):
    class TestTokenGenerator(BaseTokenGenerator):
        token_type = TokenType.ACCOUNT_ACTIVATION  # type: ignore[assignment]

    class TestTokenGenerator2(BaseTokenGenerator):
        token_type = TokenType.EMAIL_CHANGE  # type: ignore[assignment]

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

    def test_make_hash_value_includes_token_counter(self):
        timestamp = int(timezone.now().timestamp())

        self.assertIn(
            f"{self.generator.token_type}0",
            self.generator._make_hash_value(self.user, timestamp),
        )

        counter = TokenCounter.objects.create(
            user=self.user, token_type=self.generator.token_type, token_count=5
        )

        self.assertIn(
            f"{self.generator.token_type}5",
            self.generator._make_hash_value(self.user, timestamp),
        )

        counter.token_count += 1
        counter.save(update_fields=["token_count"])

        self.assertIn(
            f"{self.generator.token_type}6",
            self.generator._make_hash_value(self.user, timestamp),
        )

    def test_increment_token_counter(self):
        token_type = self.generator.token_type

        self.assertEqual(
            TokenCounter.objects.filter(user=self.user, token_type=token_type).count(),
            0,
        )

        self.generator._increment_token_counter(self.user)

        self.assertEqual(
            TokenCounter.objects.filter(user=self.user, token_type=token_type).count(),
            1,
        )

        self.generator._increment_token_counter(self.user)

        self.assertEqual(
            TokenCounter.objects.get(user=self.user, token_type=token_type).token_count,
            2,
        )

    def test_token_valid_after_creation(self):
        token = self.generator.make_token(self.user)

        self.assertEqual(TokenCounter.objects.count(), 1)
        self.assertEqual(TokenCounter.objects.first().token_count, 1)
        self.assertTrue(self.generator.check_token(self.user, token))

    def test_token_invalid_after_making_new_token(self):
        old_token = self.generator.make_token(self.user)

        self.assertTrue(self.generator.check_token(self.user, old_token))

        new_token = self.generator.make_token(self.user)

        self.assertFalse(self.generator.check_token(self.user, old_token))
        self.assertTrue(self.generator.check_token(self.user, new_token))

    def test_different_type_token_invalid(self):
        token1 = self.generator.make_token(self.user)
        token2 = self.generator2.make_token(self.user)

        self.assertFalse(self.generator.check_token(self.user, token2))
        self.assertFalse(self.generator2.check_token(self.user, token1))

    def test_token_invalid_after_counter_increment(self):
        generator2 = self.TestTokenGenerator2()

        counter1 = TokenCounter.objects.create(
            user=self.user, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=0
        )
        counter2 = TokenCounter.objects.create(
            user=self.user, token_type=TokenType.EMAIL_CHANGE, token_count=0
        )

        token1 = self.generator.make_token(self.user)
        token2 = generator2.make_token(self.user)

        self.assertTrue(self.generator.check_token(self.user, token1))
        self.assertTrue(generator2.check_token(self.user, token2))

        counter1.refresh_from_db()
        counter1.token_count += 1
        counter1.save(update_fields=["token_count"])

        self.assertFalse(self.generator.check_token(self.user, token1))
        self.assertTrue(generator2.check_token(self.user, token2))

        counter2.refresh_from_db()
        counter2.token_count += 1
        counter2.save(update_fields=["token_count"])

        self.assertFalse(self.generator.check_token(self.user, token1))
        self.assertFalse(generator2.check_token(self.user, token2))


class TestAccountActivationTokenGenerator(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

    def test_make_hash_value_includes_activation_state(self):
        TokenCounter.objects.create(
            user=self.user, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=0
        )

        generator = AccountActivationTokenGenerator()
        timestamp = int(timezone.now().timestamp())

        hash_value = generator._make_hash_value(self.user, timestamp)

        self.assertIn(f"{generator.token_type}0", hash_value)
        self.assertTrue(hash_value.endswith(str(self.user.is_active)))

    def test_token_valid_after_creation(self):
        token = activation_token_generator.make_token(self.user)

        self.assertTrue(activation_token_generator.check_token(self.user, token))

    def test_token_invalid_after_account_activation(self):
        token = activation_token_generator.make_token(self.user)

        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

        self.assertFalse(activation_token_generator.check_token(self.user, token))

    def test_new_activation_token_invalidates_previous_token(self):
        old_token = activation_token_generator.make_token(self.user)

        self.assertTrue(activation_token_generator.check_token(self.user, old_token))

        new_token = activation_token_generator.make_token(self.user)

        self.assertFalse(activation_token_generator.check_token(self.user, old_token))
        self.assertTrue(activation_token_generator.check_token(self.user, new_token))


class TestEmailChangeTokenGenerator(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.pending_email_change = PendingEmailChange.objects.create(
            user=self.user, email="new-user@test.com"
        )

    def test_make_hash_value_with_pending_email_change(self):
        generator = EmailChangeTokenGenerator()
        timestamp = int(timezone.now().timestamp())

        hash_value = generator._make_hash_value(self.user, timestamp)

        self.assertIn(f"{generator.token_type}0", hash_value)
        self.assertIn(str(self.pending_email_change.pk), hash_value)
        self.assertIn(self.pending_email_change.email.strip().lower(), hash_value)

    def test_make_hash_value_without_pending_email_change(self):
        self.pending_email_change.delete()
        self.user.refresh_from_db()

        generator = EmailChangeTokenGenerator()
        timestamp = int(timezone.now().timestamp())

        hash_value = generator._make_hash_value(self.user, timestamp)

        self.assertIn(f"{generator.token_type}0", hash_value)
        self.assertTrue(hash_value.endswith("__no_pending_email_change__"))

    def test_token_valid_after_creation(self):
        token = email_change_token_generator.make_token(self.user)

        self.assertTrue(email_change_token_generator.check_token(self.user, token))

    def test_token_invalid_after_pending_email_change(self):
        token = email_change_token_generator.make_token(self.user)

        self.pending_email_change.email = "another@test.com"
        self.pending_email_change.save(update_fields=["email"])

        self.assertFalse(email_change_token_generator.check_token(self.user, token))

    def test_token_invalid_after_pending_email_deleted(self):
        token = email_change_token_generator.make_token(self.user)

        self.pending_email_change.delete()
        self.user.refresh_from_db()

        self.assertFalse(email_change_token_generator.check_token(self.user, token))

    def test_token_invalid_after_pending_email_deleted_and_recreated_with_same_email(
        self,
    ):
        token = email_change_token_generator.make_token(self.user)

        email = self.pending_email_change.email
        self.pending_email_change.delete()
        self.user.refresh_from_db()

        PendingEmailChange.objects.create(user=self.user, email=email)
        self.user.refresh_from_db()

        self.assertFalse(email_change_token_generator.check_token(self.user, token))

    def test_token_invalid_after_counter_increment(self):
        counter = TokenCounter.objects.create(
            user=self.user, token_type=TokenType.EMAIL_CHANGE, token_count=0
        )

        token = email_change_token_generator.make_token(self.user)

        counter.refresh_from_db()
        counter.token_count += 1
        counter.save(update_fields=["token_count"])

        self.assertFalse(email_change_token_generator.check_token(self.user, token))

    def test_new_token_invalidates_previous_token(self):
        old_token = email_change_token_generator.make_token(self.user)

        self.assertTrue(email_change_token_generator.check_token(self.user, old_token))

        new_token = email_change_token_generator.make_token(self.user)

        self.assertFalse(email_change_token_generator.check_token(self.user, old_token))
        self.assertTrue(email_change_token_generator.check_token(self.user, new_token))


class TestPasswordResetTokenGenerator(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user",
            email="user@test.com",
            password="old-password-12345",
            is_active=True,
        )

    def test_password_reset_token_valid_after_creation(self):
        token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(password_reset_token_generator.check_token(self.user, token))

    def test_second_password_reset_token_invalidates_first(self):
        old_token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(
            password_reset_token_generator.check_token(self.user, old_token)
        )

        new_token = password_reset_token_generator.make_token(self.user)

        self.assertFalse(
            password_reset_token_generator.check_token(self.user, old_token)
        )
        self.assertTrue(
            password_reset_token_generator.check_token(self.user, new_token)
        )

    def test_password_reset_token_invalid_after_password_change(self):
        token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(password_reset_token_generator.check_token(self.user, token))

        self.user.set_password("new-password-12345")
        self.user.save(update_fields=["password"])

        self.assertFalse(password_reset_token_generator.check_token(self.user, token))
