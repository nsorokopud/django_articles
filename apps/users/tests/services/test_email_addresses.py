from datetime import timedelta
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from users.models import PendingEmailChange, User
from users.services.email_addresses import (
    _delete_allauth_email_addresses_for_user,
    change_email_address,
    create_pending_email_change,
    delete_expired_pending_email_changes,
    delete_expired_pending_email_changes_for_email,
    delete_pending_email_change,
    delete_social_accounts_with_email,
    is_pending_email_change_expired,
)


class TestEmailAddressServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com", password="testpass123"
        )

    def test_delete_pending_email_change_does_nothing_when_missing(self):
        self.assertEqual(PendingEmailChange.objects.count(), 0)

        delete_pending_email_change(self.test_user)

        self.assertEqual(PendingEmailChange.objects.count(), 0)

    def test_delete_pending_email_change_deletes_pending_change_for_user(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="pending@test.com"
        )

        delete_pending_email_change(self.test_user)

        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_delete_pending_email_change_does_not_delete_other_users_pending_change(
        self,
    ):
        other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )
        other_pending_email_change = PendingEmailChange.objects.create(
            user=other_user, email="other-pending@test.com"
        )

        delete_pending_email_change(self.test_user)

        self.assertTrue(
            PendingEmailChange.objects.filter(pk=other_pending_email_change.pk).exists()
        )

    def test_delete_expired_pending_email_changes_deletes_only_expired_changes(self):
        expired_user = User.objects.create_user(
            username="expired", email="expired@test.com", password="testpass123"
        )
        active_user = User.objects.create_user(
            username="active", email="active@test.com", password="testpass123"
        )
        expired_pending_email_change = PendingEmailChange.objects.create(
            user=expired_user, email="expired-pending@test.com"
        )
        active_pending_email_change = PendingEmailChange.objects.create(
            user=active_user, email="active-pending@test.com"
        )
        PendingEmailChange.objects.filter(pk=expired_pending_email_change.pk).update(
            created_at=timezone.now()
            - settings.USERS_PENDING_EMAIL_CHANGE_TTL
            - timedelta(seconds=1)
        )

        deleted_count = delete_expired_pending_email_changes()

        self.assertEqual(deleted_count, 1)
        self.assertFalse(
            PendingEmailChange.objects.filter(
                pk=expired_pending_email_change.pk
            ).exists()
        )
        self.assertTrue(
            PendingEmailChange.objects.filter(
                pk=active_pending_email_change.pk
            ).exists()
        )

    def test_is_pending_email_change_expired_returns_false_for_active_change(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="pending@test.com"
        )

        self.assertFalse(is_pending_email_change_expired(pending_email_change))

    def test_is_pending_email_change_expired_returns_true_for_expired_change(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="pending@test.com"
        )
        PendingEmailChange.objects.filter(pk=pending_email_change.pk).update(
            created_at=timezone.now()
            - settings.USERS_PENDING_EMAIL_CHANGE_TTL
            - timedelta(seconds=1)
        )
        pending_email_change.refresh_from_db()

        self.assertTrue(is_pending_email_change_expired(pending_email_change))


class TestCreatePendingEmailChange(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

    def test_creates_pending_email_change(self):
        pending_email_change = create_pending_email_change(
            user_id=self.user.id, email="new@test.com"
        )

        self.assertEqual(pending_email_change.user_id, self.user.id)
        self.assertEqual(pending_email_change.email, "new@test.com")

        self.assertTrue(
            PendingEmailChange.objects.filter(
                user=self.user, email="new@test.com"
            ).exists()
        )

    def test_create_pending_email_change_does_not_create_allauth_email_address(self):
        pending_email_change = create_pending_email_change(
            user_id=self.user.id, email="new@test.com"
        )

        self.assertEqual(pending_email_change.email, "new@test.com")
        self.assertFalse(
            EmailAddress.objects.filter(user=self.user, email="new@test.com").exists()
        )

    def test_normalizes_email_before_creating_pending_email_change(self):
        pending_email_change = create_pending_email_change(
            user_id=self.user.id, email="  New.Email@Test.COM  "
        )

        self.assertEqual(pending_email_change.email, "new.email@test.com")

    def test_deletes_expired_pending_email_change_before_creating_new_one(self):
        other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )
        expired_pending_email_change = PendingEmailChange.objects.create(
            user=other_user, email="new@test.com"
        )
        PendingEmailChange.objects.filter(pk=expired_pending_email_change.pk).update(
            created_at=timezone.now()
            - settings.USERS_PENDING_EMAIL_CHANGE_TTL
            - timedelta(seconds=1)
        )

        pending_email_change = create_pending_email_change(
            user_id=self.user.id, email="NEW@TEST.COM"
        )

        self.assertEqual(pending_email_change.user_id, self.user.id)
        self.assertEqual(pending_email_change.email, "new@test.com")
        self.assertFalse(
            PendingEmailChange.objects.filter(
                pk=expired_pending_email_change.pk
            ).exists()
        )

    def test_does_not_delete_unrelated_expired_pending_email_change(self):
        other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )
        expired_pending_email_change = PendingEmailChange.objects.create(
            user=other_user, email="unrelated@test.com"
        )
        PendingEmailChange.objects.filter(pk=expired_pending_email_change.pk).update(
            created_at=timezone.now()
            - settings.USERS_PENDING_EMAIL_CHANGE_TTL
            - timedelta(seconds=1)
        )

        pending_email_change = create_pending_email_change(
            user_id=self.user.id, email="new@test.com"
        )

        self.assertEqual(pending_email_change.user_id, self.user.id)
        self.assertEqual(pending_email_change.email, "new@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(
                pk=expired_pending_email_change.pk
            ).exists()
        )

    def test_rejects_blank_email(self):
        with self.assertRaisesMessage(ValidationError, "Email is required."):
            create_pending_email_change(user_id=self.user.id, email="   ")

        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_rejects_invalid_email(self):
        with self.assertRaises(ValidationError):
            create_pending_email_change(user_id=self.user.id, email="not-an-email")

        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_rejects_same_email_as_user_email(self):
        with self.assertRaisesMessage(
            ValidationError, "Enter a different email address."
        ):
            create_pending_email_change(user_id=self.user.id, email="USER@Test.COM")

        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_rejects_when_pending_email_change_already_exists(self):
        PendingEmailChange.objects.create(user=self.user, email="pending@test.com")

        with self.assertRaisesMessage(
            ValidationError, "There is already a pending email change."
        ):
            create_pending_email_change(user_id=self.user.id, email="another@test.com")

        self.assertFalse(
            PendingEmailChange.objects.filter(
                user=self.user, email="another@test.com"
            ).exists()
        )

    def test_rejects_email_used_by_another_user_email(self):
        User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )

        with self.assertRaisesMessage(
            ValidationError, "A user with that email already exists."
        ):
            create_pending_email_change(user_id=self.user.id, email="OTHER@Test.COM")

        self.assertFalse(
            PendingEmailChange.objects.filter(
                user=self.user, email="other@test.com"
            ).exists()
        )

    def test_rejects_email_used_by_another_pending_email_change(self):
        other_user = User.objects.create_user(
            username="other", email="other-user@test.com", password="testpass123"
        )
        PendingEmailChange.objects.create(user=other_user, email="taken@test.com")

        with self.assertRaisesMessage(
            ValidationError, "That email address is currently pending confirmation."
        ):
            create_pending_email_change(user_id=self.user.id, email="TAKEN@Test.COM")

        self.assertFalse(
            PendingEmailChange.objects.filter(
                user=self.user, email="taken@test.com"
            ).exists()
        )

    def test_database_rejects_second_pending_email_change_for_same_user(self):
        PendingEmailChange.objects.create(user=self.user, email="pending@test.com")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(
                    user=self.user, email="another@test.com"
                )

    def test_database_rejects_blank_pending_email_change_email(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(user=self.user, email="")

    def test_database_rejects_duplicate_pending_email_change_case_insensitively(self):
        other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )
        PendingEmailChange.objects.create(user=self.user, email="taken@test.com")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(
                    user=other_user, email="TAKEN@TEST.COM"
                )


class TestChangeEmailAddress(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test_user", email="test@test.com", password="testpass123"
        )
        self.token = "test-token"

    def create_pending_email_change(self, email="new@test.com"):
        return PendingEmailChange.objects.create(user=self.user, email=email)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_requires_existing_pending_email_change(self, mock_check_token):
        with self.assertRaisesMessage(
            ValidationError, "This email change request no longer exists."
        ):
            change_email_address(
                user_id=self.user.id, pending_email_change_id=999999, token=self.token
            )

        mock_check_token.assert_not_called()

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_requires_pending_email_change_for_same_user(self, mock_check_token):
        other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=other_user, email="new@test.com"
        )

        with self.assertRaisesMessage(
            ValidationError, "This email change request no longer exists."
        ):
            change_email_address(
                user_id=self.user.id,
                pending_email_change_id=pending_email_change.id,
                token=self.token,
            )

        mock_check_token.assert_not_called()

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_rejects_expired_pending_email_change(self, mock_check_token):
        pending_email_change = self.create_pending_email_change()

        PendingEmailChange.objects.filter(pk=pending_email_change.pk).update(
            created_at=timezone.now()
            - settings.USERS_PENDING_EMAIL_CHANGE_TTL
            - timedelta(seconds=1)
        )

        with self.assertRaisesMessage(
            ValidationError, "This email change link has expired."
        ):
            change_email_address(
                user_id=self.user.id,
                pending_email_change_id=pending_email_change.id,
                token=self.token,
            )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        mock_check_token.assert_not_called()

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_rejects_invalid_token(self, mock_check_token):
        mock_check_token.return_value = False
        pending_email_change = self.create_pending_email_change()

        with self.assertRaisesMessage(ValidationError, "Invalid email change link."):
            change_email_address(
                user_id=self.user.id,
                pending_email_change_id=pending_email_change.id,
                token=self.token,
            )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_does_not_require_allauth_email_address(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change()

        self.assertFalse(EmailAddress.objects.filter(user=self.user).exists())

        change_email_address(
            user_id=self.user.id,
            pending_email_change_id=pending_email_change.id,
            token=self.token,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@test.com")
        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_lowercases_user_email_and_deletes_pending_change(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change(email="E2@TEST.COM")

        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="123",
            extra_data={"email": self.user.email},
        )

        self.assertEqual(SocialAccount.objects.count(), 1)

        change_email_address(
            user_id=self.user.id,
            pending_email_change_id=pending_email_change.id,
            token=self.token,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "e2@test.com")
        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        self.assertEqual(SocialAccount.objects.count(), 0)
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_invalidates_user_sessions_after_email_change(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change()

        self.assertEqual(self.user.session_auth_version, 0)

        change_email_address(
            user_id=self.user.id,
            pending_email_change_id=pending_email_change.id,
            token=self.token,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.session_auth_version, 1)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_does_not_invalidate_sessions_when_token_invalid(self, mock_check_token):
        mock_check_token.return_value = False
        pending_email_change = self.create_pending_email_change()

        original_session_auth_version = self.user.session_auth_version

        with self.assertRaisesMessage(ValidationError, "Invalid email change link."):
            change_email_address(
                user_id=self.user.id,
                pending_email_change_id=pending_email_change.id,
                token=self.token,
            )

        self.user.refresh_from_db()
        self.assertEqual(self.user.session_auth_version, original_session_auth_version)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_deletes_only_social_accounts_matching_old_email(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change()

        matching_account = SocialAccount.objects.create(
            user=self.user,
            provider="matching",
            uid="123",
            extra_data={"email": "TEST@TEST.COM"},
        )
        non_matching_account = SocialAccount.objects.create(
            user=self.user,
            provider="non_matching",
            uid="456",
            extra_data={"email": "other@test.com"},
        )

        change_email_address(
            user_id=self.user.id,
            pending_email_change_id=pending_email_change.id,
            token=self.token,
        )

        self.assertFalse(SocialAccount.objects.filter(pk=matching_account.pk).exists())
        self.assertTrue(
            SocialAccount.objects.filter(pk=non_matching_account.pk).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_deletes_stale_same_email_pending_change(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change(email="TEST@TEST.COM")

        change_email_address(
            user_id=self.user.id,
            pending_email_change_id=pending_email_change.id,
            token=self.token,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@test.com")
        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_deletes_allauth_email_addresses_for_user(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change()

        old_email_address = EmailAddress.objects.create(
            user=self.user, email="test@test.com", verified=True, primary=True
        )
        extra_email_address = EmailAddress.objects.create(
            user=self.user, email="other@test.com", verified=True, primary=False
        )

        change_email_address(
            user_id=self.user.id,
            pending_email_change_id=pending_email_change.id,
            token=self.token,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@test.com")
        self.assertFalse(
            EmailAddress.objects.filter(
                pk__in=[old_email_address.pk, extra_email_address.pk]
            ).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_raises_validation_error_when_pending_email_invalid(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change(email="valid@test.com")

        # Simulate dirty data bypassing model/form validation.
        PendingEmailChange.objects.filter(pk=pending_email_change.pk).update(
            email="not-an-email"
        )

        with self.assertRaises(ValidationError):
            change_email_address(
                user_id=self.user.id,
                pending_email_change_id=pending_email_change.id,
                token=self.token,
            )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_rejects_email_taken_after_pending_change_created(self, mock_check_token):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change()

        User.objects.create_user(username="other", email="new@test.com")

        with self.assertRaisesMessage(
            ValidationError, "This email address is no longer available."
        ):
            change_email_address(
                user_id=self.user.id,
                pending_email_change_id=pending_email_change.id,
                token=self.token,
            )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)

    @patch("users.services.email_addresses.email_change_token_generator.check_token")
    def test_rejects_email_taken_after_pending_change_created_ci(
        self, mock_check_token
    ):
        mock_check_token.return_value = True
        pending_email_change = self.create_pending_email_change()

        User.objects.create_user(username="other", email="NEW@TEST.COM")

        with self.assertRaisesMessage(
            ValidationError, "This email address is no longer available."
        ):
            change_email_address(
                user_id=self.user.id,
                pending_email_change_id=pending_email_change.id,
                token=self.token,
            )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        mock_check_token.assert_called_once_with(self.user, self.token)


class TestDeleteSocialAccountsWithEmail(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )

    def test_raises_when_called_outside_transaction(self):
        with self.assertRaisesMessage(
            transaction.TransactionManagementError,
            "This function must be called inside an atomic transaction.",
        ):
            delete_social_accounts_with_email(
                user_id=self.user.id, email="email@test.com"
            )

    def test_deletes_matching_social_accounts_inside_transaction(self):
        email = "email@test.com"
        other_email = "email2@test.com"

        SocialAccount.objects.bulk_create(
            [
                SocialAccount(
                    user=self.user,
                    provider="p1",
                    uid="123",
                    extra_data={"email": email},
                ),
                SocialAccount(
                    user=self.user,
                    provider="p2",
                    uid="456",
                    extra_data={"email": "EMAIL@TEST.COM"},
                ),
                SocialAccount(
                    user=self.user,
                    provider="p3",
                    uid="789",
                    extra_data={"email": other_email},
                ),
                SocialAccount(
                    user=self.other_user,
                    provider="p4",
                    uid="111",
                    extra_data={"email": email},
                ),
            ]
        )

        with transaction.atomic():
            delete_social_accounts_with_email(
                user_id=self.user.id, email="nonexistent@test.com"
            )

        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.user, extra_data__email=email
            ).count(),
            1,
        )
        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.user, extra_data__email="EMAIL@TEST.COM"
            ).count(),
            1,
        )
        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.user, extra_data__email=other_email
            ).count(),
            1,
        )
        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.other_user, extra_data__email=email
            ).count(),
            1,
        )

        with transaction.atomic():
            delete_social_accounts_with_email(user_id=self.user.id, email=email)

        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.user, extra_data__email=email
            ).count(),
            0,
        )
        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.user, extra_data__email="EMAIL@TEST.COM"
            ).count(),
            0,
        )
        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.user, extra_data__email=other_email
            ).count(),
            1,
        )
        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.other_user, extra_data__email=email
            ).count(),
            1,
        )

    def test_ignores_social_accounts_without_email_extra_data(self):
        account_without_email = SocialAccount.objects.create(
            user=self.user, provider="p1", uid="123", extra_data={}
        )

        with transaction.atomic():
            delete_social_accounts_with_email(
                user_id=self.user.id, email="email@test.com"
            )

        self.assertTrue(
            SocialAccount.objects.filter(pk=account_without_email.pk).exists()
        )


class TestDeleteAllauthEmailAddressesForUser(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )

    def test_raises_when_called_outside_transaction(self):
        with self.assertRaisesMessage(
            transaction.TransactionManagementError,
            "This function must be called inside an atomic transaction.",
        ):
            _delete_allauth_email_addresses_for_user(user_id=self.user.id)

    def test_deletes_only_users_allauth_email_addresses_inside_transaction(self):
        email_address = EmailAddress.objects.create(
            user=self.user, email="user@test.com", verified=True, primary=True
        )
        extra_email_address = EmailAddress.objects.create(
            user=self.user, email="extra@test.com", verified=False, primary=False
        )
        other_email_address = EmailAddress.objects.create(
            user=self.other_user, email="other@test.com", verified=True, primary=True
        )

        with transaction.atomic():
            _delete_allauth_email_addresses_for_user(user_id=self.user.id)

        self.assertFalse(
            EmailAddress.objects.filter(
                pk__in=[email_address.pk, extra_email_address.pk]
            ).exists()
        )
        self.assertTrue(EmailAddress.objects.filter(pk=other_email_address.pk).exists())


class TestDeleteExpiredPendingEmailChanges(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", email="user1@test.com")
        self.user2 = User.objects.create_user(username="other", email="user2@test.com")

    def _expire(self, pending_email_change):
        PendingEmailChange.objects.filter(pk=pending_email_change.pk).update(
            created_at=timezone.now()
            - settings.USERS_PENDING_EMAIL_CHANGE_TTL
            - timedelta(seconds=1)
        )

    def test_delete_expired_pending_email_changes_deletes_all_expired_rows(self):
        expired_one = PendingEmailChange.objects.create(
            user=self.user1, email="one@test.com"
        )
        expired_two = PendingEmailChange.objects.create(
            user=self.user2, email="two@test.com"
        )

        self._expire(expired_one)
        self._expire(expired_two)

        deleted_count = delete_expired_pending_email_changes()

        self.assertEqual(deleted_count, 2)
        self.assertFalse(PendingEmailChange.objects.filter(pk=expired_one.pk).exists())
        self.assertFalse(PendingEmailChange.objects.filter(pk=expired_two.pk).exists())

    def test_delete_expired_pending_email_changes_keeps_non_expired_rows(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.user1, email="new@test.com"
        )

        deleted_count = delete_expired_pending_email_changes()

        self.assertEqual(deleted_count, 0)
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_delete_expired_pending_email_changes_for_email_deletes_only_matching_email(
        self,
    ):
        matching = PendingEmailChange.objects.create(
            user=self.user1, email="target1@test.com"
        )
        unrelated = PendingEmailChange.objects.create(
            user=self.user2, email="target2@test.com"
        )

        self._expire(matching)
        self._expire(unrelated)

        deleted_count = delete_expired_pending_email_changes_for_email(
            email="TARGET1@Test.COM"
        )

        self.assertEqual(deleted_count, 1)
        self.assertFalse(PendingEmailChange.objects.filter(pk=matching.pk).exists())
        self.assertTrue(PendingEmailChange.objects.filter(pk=unrelated.pk).exists())

    def test_delete_expired_pending_email_changes_for_email_keeps_non_expired_match(
        self,
    ):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.user1, email="target@test.com"
        )

        deleted_count = delete_expired_pending_email_changes_for_email(
            email="target@test.com"
        )

        self.assertEqual(deleted_count, 0)
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_delete_expired_pending_email_changes_for_email_ignores_blank_email(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.user1, email="target@test.com"
        )
        self._expire(pending_email_change)

        deleted_count = delete_expired_pending_email_changes_for_email(email="   ")

        self.assertEqual(deleted_count, 0)
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
