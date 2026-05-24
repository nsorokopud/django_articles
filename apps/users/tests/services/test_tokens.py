from django.test import TestCase
from django.utils import timezone

from users.models import PendingEmailChange, User
from users.services.tokens import (
    AccountActivationTokenGenerator,
    CustomPasswordResetTokenGenerator,
    EmailChangeTokenGenerator,
    activation_token_generator,
    advance_password_reset_token_version,
    email_change_token_generator,
    password_reset_token_generator,
)

from ...normalization import normalize_email


class TestAccountActivationTokenGenerator(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

    def test_make_hash_value_includes_activation_state(self):
        generator = AccountActivationTokenGenerator()
        timestamp = int(timezone.now().timestamp())

        hash_value = generator._make_hash_value(self.user, timestamp)

        self.assertTrue(hash_value.endswith(str(self.user.is_active)))

    def test_token_valid_after_creation(self):
        token = activation_token_generator.make_token(self.user)

        self.assertTrue(activation_token_generator.check_token(self.user, token))

    def test_multiple_activation_tokens_are_valid_before_activation(self):
        old_token = activation_token_generator.make_token(self.user)

        self.assertTrue(activation_token_generator.check_token(self.user, old_token))

        new_token = activation_token_generator.make_token(self.user)

        self.assertTrue(activation_token_generator.check_token(self.user, old_token))
        self.assertTrue(activation_token_generator.check_token(self.user, new_token))

    def test_token_invalid_after_account_activation(self):
        token = activation_token_generator.make_token(self.user)

        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

        self.assertFalse(activation_token_generator.check_token(self.user, token))

    def test_all_existing_activation_tokens_invalid_after_account_activation(self):
        old_token = activation_token_generator.make_token(self.user)
        new_token = activation_token_generator.make_token(self.user)

        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

        self.assertFalse(activation_token_generator.check_token(self.user, old_token))
        self.assertFalse(activation_token_generator.check_token(self.user, new_token))


class TestEmailChangeTokenGenerator(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.pending_email_change = PendingEmailChange.objects.create(
            user=self.user,
            email="new-user@test.com",
        )

    def test_make_hash_value_with_pending_email_change(self):
        generator = EmailChangeTokenGenerator()
        timestamp = int(timezone.now().timestamp())

        hash_value = generator._make_hash_value(self.user, timestamp)

        self.assertIn(str(self.pending_email_change.pk), hash_value)
        self.assertIn(normalize_email(self.pending_email_change.email), hash_value)

    def test_make_hash_value_without_pending_email_change(self):
        self.pending_email_change.delete()
        self.user.refresh_from_db()

        generator = EmailChangeTokenGenerator()
        timestamp = int(timezone.now().timestamp())

        hash_value = generator._make_hash_value(self.user, timestamp)

        self.assertTrue(hash_value.endswith("__no_pending_email_change__"))

    def test_token_valid_after_creation(self):
        token = email_change_token_generator.make_token(self.user)

        self.assertTrue(email_change_token_generator.check_token(self.user, token))

    def test_multiple_email_change_tokens_are_valid_for_same_pending_change(self):
        old_token = email_change_token_generator.make_token(self.user)

        self.assertTrue(email_change_token_generator.check_token(self.user, old_token))

        new_token = email_change_token_generator.make_token(self.user)

        self.assertTrue(email_change_token_generator.check_token(self.user, old_token))
        self.assertTrue(email_change_token_generator.check_token(self.user, new_token))

    def test_token_invalid_after_pending_email_change(self):
        token = email_change_token_generator.make_token(self.user)

        self.pending_email_change.email = "another@test.com"
        self.pending_email_change.save(update_fields=["email"])

        self.assertFalse(email_change_token_generator.check_token(self.user, token))

    def test_all_existing_tokens_invalid_after_pending_email_change(self):
        old_token = email_change_token_generator.make_token(self.user)
        new_token = email_change_token_generator.make_token(self.user)

        self.pending_email_change.email = "another@test.com"
        self.pending_email_change.save(update_fields=["email"])

        self.assertFalse(email_change_token_generator.check_token(self.user, old_token))
        self.assertFalse(email_change_token_generator.check_token(self.user, new_token))

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


class TestPasswordResetTokenGenerator(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="u@test.com", password="pass-12345", is_active=True
        )

    def test_make_hash_value_includes_password_reset_token_version(self):
        generator = CustomPasswordResetTokenGenerator()
        timestamp = int(timezone.now().timestamp())

        self.user.password_reset_token_version = 0
        hash_value = generator._make_hash_value(self.user, timestamp)
        self.assertTrue(hash_value.endswith("0"))

        self.user.password_reset_token_version = 7
        hash_value = generator._make_hash_value(self.user, timestamp)
        self.assertTrue(hash_value.endswith("7"))

    def test_password_reset_token_valid_after_creation(self):
        token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(password_reset_token_generator.check_token(self.user, token))

    def test_multiple_password_reset_tokens_are_valid_without_version_advance(self):
        old_token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(
            password_reset_token_generator.check_token(self.user, old_token)
        )

        new_token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(
            password_reset_token_generator.check_token(self.user, old_token)
        )
        self.assertTrue(
            password_reset_token_generator.check_token(self.user, new_token)
        )

    def test_password_reset_token_invalid_after_version_advance(self):
        old_token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(
            password_reset_token_generator.check_token(self.user, old_token)
        )

        self.user = advance_password_reset_token_version(user_id=self.user.id)

        new_token = password_reset_token_generator.make_token(self.user)

        self.assertFalse(
            password_reset_token_generator.check_token(self.user, old_token)
        )
        self.assertTrue(
            password_reset_token_generator.check_token(self.user, new_token)
        )

    def test_increments_and_returns_fresh_user(self):
        self.assertEqual(self.user.password_reset_token_version, 0)

        updated_user = advance_password_reset_token_version(user_id=self.user.id)

        self.assertEqual(updated_user.password_reset_token_version, 1)

        self.user.refresh_from_db()
        self.assertEqual(self.user.password_reset_token_version, 1)

    def test_token_invalid_after_password_change(self):
        token = password_reset_token_generator.make_token(self.user)

        self.assertTrue(password_reset_token_generator.check_token(self.user, token))

        self.user.set_password("new-password-12345")
        self.user.save(update_fields=["password"])

        self.assertFalse(password_reset_token_generator.check_token(self.user, token))
