from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from users.models import PendingEmailChange, User
from users.services import change_email_address
from users.services.email_addresses import (
    _delete_allauth_email_addresses_for_user,
    create_pending_email_change,
    delete_pending_email_change,
    delete_social_accounts_with_email,
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

    def test_change_email_address_requires_existing_pending_email_change(self):
        with self.assertRaisesMessage(
            ValidationError, "This email change request no longer exists."
        ):
            change_email_address(
                user_id=self.test_user.id, pending_email_change_id=999999
            )

    def test_change_email_address_requires_pending_email_change_for_same_user(self):
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
                user_id=self.test_user.id,
                pending_email_change_id=pending_email_change.id,
            )

    def test_change_email_address_does_not_require_allauth_email_address(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="new@test.com"
        )

        self.assertFalse(EmailAddress.objects.filter(user=self.test_user).exists())

        change_email_address(
            user_id=self.test_user.id, pending_email_change_id=pending_email_change.id
        )

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "new@test.com")

    def test_change_email_address_lowercases_user_email_and_deletes_pending_change(
        self,
    ):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="E2@TEST.COM"
        )
        SocialAccount.objects.create(
            user=self.test_user,
            provider="google",
            uid="123",
            extra_data={"email": self.test_user.email},
        )

        self.assertEqual(SocialAccount.objects.count(), 1)

        change_email_address(
            user_id=self.test_user.id, pending_email_change_id=pending_email_change.id
        )

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "e2@test.com")

        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        self.assertEqual(SocialAccount.objects.count(), 0)

    def test_change_email_address_deletes_only_social_accounts_matching_old_email(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="new@test.com"
        )

        matching_account = SocialAccount.objects.create(
            user=self.test_user,
            provider="matching",
            uid="123",
            extra_data={"email": "TEST@TEST.COM"},
        )
        non_matching_account = SocialAccount.objects.create(
            user=self.test_user,
            provider="non_matching",
            uid="456",
            extra_data={"email": "other@test.com"},
        )

        change_email_address(
            user_id=self.test_user.id, pending_email_change_id=pending_email_change.id
        )

        self.assertFalse(SocialAccount.objects.filter(pk=matching_account.pk).exists())
        self.assertTrue(
            SocialAccount.objects.filter(pk=non_matching_account.pk).exists()
        )

    def test_change_email_address_deletes_stale_same_email_pending_change(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="TEST@TEST.COM"
        )

        change_email_address(
            user_id=self.test_user.id, pending_email_change_id=pending_email_change.id
        )

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "test@test.com")
        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_change_email_address_deletes_allauth_email_addresses_for_user(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="new@test.com"
        )
        old_email_address = EmailAddress.objects.create(
            user=self.test_user, email="test@test.com", verified=True, primary=True
        )
        extra_email_address = EmailAddress.objects.create(
            user=self.test_user, email="other@test.com", verified=True, primary=False
        )

        change_email_address(
            user_id=self.test_user.id, pending_email_change_id=pending_email_change.id
        )

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "new@test.com")
        self.assertFalse(
            EmailAddress.objects.filter(
                pk__in=[old_email_address.pk, extra_email_address.pk]
            ).exists()
        )

    def test_change_email_address_raises_validation_error_when_pending_email_invalid(
        self,
    ):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="valid@test.com"
        )

        # Simulate dirty data bypassing model/form validation.
        PendingEmailChange.objects.filter(pk=pending_email_change.pk).update(
            email="not-an-email"
        )

        with self.assertRaises(ValidationError):
            change_email_address(
                user_id=self.test_user.id,
                pending_email_change_id=pending_email_change.id,
            )

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_change_email_address_rejects_email_taken_after_pending_change_created(
        self,
    ):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="new@test.com"
        )

        User.objects.create_user(username="other", email="new@test.com")

        with self.assertRaisesMessage(
            ValidationError, "This email address is no longer available."
        ):
            change_email_address(
                user_id=self.test_user.id,
                pending_email_change_id=pending_email_change.id,
            )

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_change_email_address_rejects_email_taken_after_pending_change_created_ci(
        self,
    ):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="new@test.com"
        )

        User.objects.create_user(username="other", email="NEW@TEST.COM")

        with self.assertRaisesMessage(
            ValidationError, "This email address is no longer available."
        ):
            change_email_address(
                user_id=self.test_user.id,
                pending_email_change_id=pending_email_change.id,
            )

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "test@test.com")
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )


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
            ValidationError,
            "That email address is currently pending confirmation.",
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


class TestUserEmailConstraints(TestCase):
    def test_blank_email_is_rejected_by_database(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(pk=user.pk).update(email="")

    def test_duplicate_user_email_is_rejected_case_insensitively(self):
        User.objects.create_user(
            username="user1", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="user2", email="USER@TEST.COM", password="testpass123"
                )


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
