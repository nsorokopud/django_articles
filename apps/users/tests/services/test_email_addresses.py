from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from users.models import User
from users.services import (
    change_email_address,
    create_pending_email_address,
    delete_pending_email_address,
    enforce_single_current_and_pending_email_per_user,
)
from users.services.email_addresses import (
    delete_social_accounts_with_email,
    sync_primary_email_address_for_user,
)


class TestEmailAddressServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com", password="testpass123"
        )

    def test_delete_pending_email_address_deletes_non_primary_email_only(self):
        self.assertEqual(EmailAddress.objects.count(), 0)

        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 0)

        primary_email = EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )

        delete_pending_email_address(self.test_user)

        self.assertEqual(EmailAddress.objects.count(), 1)
        self.assertTrue(EmailAddress.objects.filter(pk=primary_email.pk).exists())

        pending_email = EmailAddress.objects.create(
            user=self.test_user, email="pending@test.com", primary=False, verified=False
        )

        delete_pending_email_address(self.test_user)

        self.assertEqual(EmailAddress.objects.count(), 1)
        self.assertTrue(EmailAddress.objects.filter(pk=primary_email.pk).exists())
        self.assertFalse(EmailAddress.objects.filter(pk=pending_email.pk).exists())

    def test_delete_pending_email_address_deletes_verified_non_primary_email_too(self):
        EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        pending_email = EmailAddress.objects.create(
            user=self.test_user, email="pending@test.com", primary=False, verified=True
        )

        delete_pending_email_address(self.test_user)

        self.assertFalse(EmailAddress.objects.filter(pk=pending_email.pk).exists())
        self.assertEqual(EmailAddress.objects.filter(user=self.test_user).count(), 1)

    def test_change_email_address_requires_exactly_one_primary_email(self):
        EmailAddress.objects.create(
            user=self.test_user, email="pending@test.com", primary=False, verified=False
        )

        with self.assertRaisesMessage(
            ValidationError, "Expected exactly one primary email address."
        ):
            change_email_address(self.test_user.id)

    def test_change_email_address_requires_exactly_one_pending_email_change(self):
        EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )

        with self.assertRaisesMessage(
            ValidationError, "Expected exactly one pending email change."
        ):
            change_email_address(self.test_user.id)

    def test_change_email_address_lowercases_user_email_and_promotes_pending_email(
        self,
    ):
        old_email = EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        pending_email = EmailAddress.objects.create(
            user=self.test_user, email="E2@TEST.COM", primary=False, verified=False
        )
        SocialAccount.objects.create(
            user=self.test_user,
            provider="p1",
            uid="123",
            extra_data={"email": old_email.email},
        )

        self.assertEqual(SocialAccount.objects.count(), 1)

        change_email_address(self.test_user.id)

        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, "e2@test.com")

        pending_email.refresh_from_db()
        self.assertEqual(pending_email.email, "e2@test.com")
        self.assertTrue(pending_email.primary)
        self.assertTrue(pending_email.verified)

        with self.assertRaises(EmailAddress.DoesNotExist):
            EmailAddress.objects.get(pk=old_email.pk)

        self.assertEqual(SocialAccount.objects.count(), 0)

    def test_change_email_address_deletes_only_social_accounts_matching_old_email(self):
        EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        EmailAddress.objects.create(
            user=self.test_user, email="new@test.com", primary=False, verified=False
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

        change_email_address(self.test_user.id)

        self.assertFalse(SocialAccount.objects.filter(pk=matching_account.pk).exists())
        self.assertTrue(
            SocialAccount.objects.filter(pk=non_matching_account.pk).exists()
        )


class TestCreatePendingEmailAddress(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        EmailAddress.objects.create(
            user=self.user, email="user@test.com", verified=True, primary=True
        )

    def test_creates_pending_email_address(self):
        email_address = create_pending_email_address(
            user_id=self.user.id, email="new@test.com"
        )

        self.assertEqual(email_address.user_id, self.user.id)
        self.assertEqual(email_address.email, "new@test.com")
        self.assertFalse(email_address.primary)
        self.assertFalse(email_address.verified)

        self.assertTrue(
            EmailAddress.objects.filter(
                user=self.user, email="new@test.com", primary=False, verified=False
            ).exists()
        )

    def test_normalizes_email_before_creating_pending_email_address(self):
        email_address = create_pending_email_address(
            user_id=self.user.id, email="  New.Email@Test.COM  "
        )

        self.assertEqual(email_address.email, "new.email@test.com")

    def test_rejects_blank_email(self):
        with self.assertRaisesMessage(ValidationError, "Email is required."):
            create_pending_email_address(user_id=self.user.id, email="   ")

        self.assertEqual(
            EmailAddress.objects.filter(user=self.user, primary=False).count(), 0
        )

    def test_rejects_invalid_email(self):
        with self.assertRaises(ValidationError):
            create_pending_email_address(user_id=self.user.id, email="not-an-email")

        self.assertEqual(
            EmailAddress.objects.filter(user=self.user, primary=False).count(), 0
        )

    def test_rejects_same_email_as_user_email(self):
        with self.assertRaisesMessage(
            ValidationError, "Enter a different email address."
        ):
            create_pending_email_address(user_id=self.user.id, email="USER@Test.COM")

        self.assertEqual(
            EmailAddress.objects.filter(user=self.user, primary=False).count(), 0
        )

    def test_rejects_when_pending_email_change_already_exists(self):
        EmailAddress.objects.create(
            user=self.user, email="pending@test.com", verified=False, primary=False
        )

        with self.assertRaisesMessage(
            ValidationError, "There is already a pending email change."
        ):
            create_pending_email_address(user_id=self.user.id, email="another@test.com")

        self.assertFalse(
            EmailAddress.objects.filter(
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
            create_pending_email_address(user_id=self.user.id, email="OTHER@Test.COM")

        self.assertFalse(
            EmailAddress.objects.filter(
                user=self.user, email="other@test.com", primary=False
            ).exists()
        )

    def test_rejects_email_used_by_another_email_address(self):
        other_user = User.objects.create_user(
            username="other", email="other-user@test.com", password="testpass123"
        )
        EmailAddress.objects.create(
            user=other_user, email="taken@test.com", verified=True, primary=True
        )

        with self.assertRaisesMessage(
            ValidationError, "A user with that email already exists."
        ):
            create_pending_email_address(user_id=self.user.id, email="TAKEN@Test.COM")

        self.assertFalse(
            EmailAddress.objects.filter(
                user=self.user, email="taken@test.com", primary=False
            ).exists()
        )

    def test_rejects_when_same_user_already_has_non_primary_email_address(self):
        EmailAddress.objects.create(
            user=self.user, email="old-secondary@test.com", verified=True, primary=False
        )

        with self.assertRaisesMessage(
            ValidationError, "There is already a pending email change."
        ):
            create_pending_email_address(user_id=self.user.id, email="new@test.com")

        self.assertFalse(
            EmailAddress.objects.filter(user=self.user, email="new@test.com").exists()
        )


class TestEnforceSingleCurrentAndPendingEmailPerUser(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="test@test.com", password="testpass123"
        )

    def test_allows_one_current_and_one_pending_email(self):
        EmailAddress.objects.create(
            user=self.user, email="test@test.com", primary=True, verified=True
        )

        pending_email = EmailAddress(
            user=self.user, email="Pending@TEST.COM", primary=False, verified=False
        )

        enforce_single_current_and_pending_email_per_user(pending_email)

        self.assertEqual(pending_email.email, "pending@test.com")

    def test_rejects_second_primary_email_for_same_user(self):
        EmailAddress.objects.create(
            user=self.user, email="primary@test.com", primary=True, verified=True
        )

        second_primary = EmailAddress(
            user=self.user, email="second-primary@test.com", primary=True, verified=True
        )

        with self.assertRaises(ValidationError) as context:
            enforce_single_current_and_pending_email_per_user(second_primary)

        self.assertEqual(
            context.exception.messages,
            ["This user already has a primary email address."],
        )

    def test_rejects_second_pending_email_for_same_user(self):
        EmailAddress.objects.create(
            user=self.user, email="pending1@test.com", primary=False, verified=False
        )

        second_pending = EmailAddress(
            user=self.user, email="pending2@test.com", primary=False, verified=False
        )

        with self.assertRaises(ValidationError) as context:
            enforce_single_current_and_pending_email_per_user(second_pending)

        self.assertEqual(
            context.exception.messages,
            ["This user already has a pending email address."],
        )

    def test_allows_many_unsaved_instances_because_only_saved_rows_count(self):
        email1 = EmailAddress(user=self.user, email="E1@TEST.COM", primary=True)
        email2 = EmailAddress(user=self.user, email="E2@TEST.COM", primary=True)
        email3 = EmailAddress(user=self.user, email="E3@TEST.COM", primary=True)

        enforce_single_current_and_pending_email_per_user(email1)
        enforce_single_current_and_pending_email_per_user(email2)
        enforce_single_current_and_pending_email_per_user(email3)

        self.assertEqual(email1.email, "e1@test.com")
        self.assertEqual(email2.email, "e2@test.com")
        self.assertEqual(email3.email, "e3@test.com")

        email4 = EmailAddress(user=self.user, email="E4@TEST.COM", primary=False)
        email5 = EmailAddress(user=self.user, email="E5@TEST.COM", primary=False)
        email6 = EmailAddress(user=self.user, email="E6@TEST.COM", primary=False)

        enforce_single_current_and_pending_email_per_user(email4)
        enforce_single_current_and_pending_email_per_user(email5)
        enforce_single_current_and_pending_email_per_user(email6)

        self.assertEqual(email4.email, "e4@test.com")
        self.assertEqual(email5.email, "e5@test.com")
        self.assertEqual(email6.email, "e6@test.com")

    def test_rejects_email_used_by_another_user_email_case_insensitively(self):
        User.objects.create_user(
            username="other", email="taken@test.com", password="testpass123"
        )

        email = EmailAddress(
            user=self.user, email="TAKEN@TEST.COM", primary=False, verified=False
        )

        with self.assertRaises(ValidationError) as context:
            enforce_single_current_and_pending_email_per_user(email)

        self.assertEqual(
            context.exception.messages, ["A user with that email already exists."]
        )

    def test_rejects_email_used_by_another_users_email_address_case_insensitively(self):
        other_user = User.objects.create_user(
            username="other", email="other@test.com", password="testpass123"
        )
        EmailAddress.objects.create(
            user=other_user, email="taken@test.com", primary=True, verified=True
        )

        email = EmailAddress(
            user=self.user, email="TAKEN@TEST.COM", primary=False, verified=False
        )

        with self.assertRaises(ValidationError) as context:
            enforce_single_current_and_pending_email_per_user(email)

        self.assertEqual(
            context.exception.messages, ["A user with that email already exists."]
        )

    def test_existing_instance_excludes_itself(self):
        email = EmailAddress.objects.create(
            user=self.user, email="primary@test.com", primary=True, verified=True
        )

        email.email = "PRIMARY@TEST.COM"

        enforce_single_current_and_pending_email_per_user(email)

        self.assertEqual(email.email, "primary@test.com")


class TestSyncPrimaryEmailAddressForUser(TestCase):
    def test_creates_verified_primary_email_address_when_missing(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 0)

        email_address = sync_primary_email_address_for_user(user_id=user.id)

        user.refresh_from_db()
        email_address.refresh_from_db()

        self.assertEqual(user.email, "user@test.com")
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)
        self.assertEqual(email_address.user_id, user.id)
        self.assertEqual(email_address.email, "user@test.com")
        self.assertTrue(email_address.verified)
        self.assertTrue(email_address.primary)

    def test_normalizes_user_email_and_creates_matching_email_address(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        # Simulate dirty existing data bypassing User.save().
        User.objects.filter(pk=user.pk).update(email="  User.Abc@Test.COM  ")

        email_address = sync_primary_email_address_for_user(user_id=user.id)

        user.refresh_from_db()
        email_address.refresh_from_db()

        self.assertEqual(user.email, "user.abc@test.com")
        self.assertEqual(email_address.email, "user.abc@test.com")
        self.assertTrue(email_address.verified)
        self.assertTrue(email_address.primary)

    def test_updates_existing_matching_email_address(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        email_address = EmailAddress.objects.create(
            user=user, email="user@test.com", verified=False, primary=False
        )

        result = sync_primary_email_address_for_user(user_id=user.id)

        email_address.refresh_from_db()
        result.refresh_from_db()

        self.assertEqual(result.id, email_address.id)
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

        self.assertEqual(email_address.email, "user@test.com")
        self.assertTrue(email_address.verified)
        self.assertTrue(email_address.primary)

    def test_matches_existing_email_address_case_insensitively(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        email_address = EmailAddress.objects.create(
            user=user, email="USER@TEST.COM", verified=False, primary=False
        )

        result = sync_primary_email_address_for_user(user_id=user.id)

        email_address.refresh_from_db()
        result.refresh_from_db()

        self.assertEqual(result.id, email_address.id)
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)
        self.assertEqual(email_address.email, "user@test.com")
        self.assertTrue(email_address.verified)
        self.assertTrue(email_address.primary)

    def test_removes_existing_primary_email_address_when_different_email_matches_user(
        self,
    ):
        user = User.objects.create_user(
            username="user", email="new@test.com", password="testpass123"
        )
        old_primary = EmailAddress.objects.create(
            user=user, email="old@test.com", verified=True, primary=True
        )
        matching_email = EmailAddress.objects.create(
            user=user, email="new@test.com", verified=False, primary=False
        )

        result = sync_primary_email_address_for_user(user_id=user.id)

        matching_email.refresh_from_db()
        result.refresh_from_db()

        self.assertEqual(result.id, matching_email.id)

        self.assertFalse(EmailAddress.objects.filter(pk=old_primary.pk).exists())

        self.assertTrue(matching_email.primary)
        self.assertTrue(matching_email.verified)
        self.assertEqual(matching_email.email, "new@test.com")

        self.assertEqual(
            EmailAddress.objects.filter(user=user, primary=True).count(), 1
        )
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

    def test_removes_existing_primary_email_address_and_creates_matching_email(self):
        user = User.objects.create_user(
            username="user", email="new@test.com", password="testpass123"
        )
        old_primary = EmailAddress.objects.create(
            user=user, email="old@test.com", verified=True, primary=True
        )

        result = sync_primary_email_address_for_user(user_id=user.id)

        result.refresh_from_db()

        self.assertFalse(EmailAddress.objects.filter(pk=old_primary.pk).exists())

        self.assertEqual(result.user_id, user.id)
        self.assertEqual(result.email, "new@test.com")
        self.assertTrue(result.primary)
        self.assertTrue(result.verified)

        self.assertEqual(
            EmailAddress.objects.filter(user=user, primary=True).count(), 1
        )
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

    def test_removes_stale_non_matching_email_addresses(self):
        user = User.objects.create_user(
            username="user", email="current@test.com", password="testpass123"
        )
        stale_primary = EmailAddress.objects.create(
            user=user, email="old@test.com", verified=True, primary=True
        )
        stale_pending = EmailAddress.objects.create(
            user=user, email="pending@test.com", verified=False, primary=False
        )

        result = sync_primary_email_address_for_user(user_id=user.id)

        result.refresh_from_db()

        self.assertFalse(EmailAddress.objects.filter(pk=stale_primary.pk).exists())
        self.assertFalse(EmailAddress.objects.filter(pk=stale_pending.pk).exists())

        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)
        self.assertEqual(result.email, "current@test.com")
        self.assertTrue(result.primary)
        self.assertTrue(result.verified)

    def test_is_idempotent(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        first_result = sync_primary_email_address_for_user(user_id=user.id)
        second_result = sync_primary_email_address_for_user(user_id=user.id)

        first_result.refresh_from_db()
        second_result.refresh_from_db()

        self.assertEqual(first_result.id, second_result.id)
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

        allauth_email = EmailAddress.objects.get(user=user)
        self.assertEqual(allauth_email.email, "user@test.com")
        self.assertTrue(allauth_email.verified)
        self.assertTrue(allauth_email.primary)

    def test_raises_validation_error_when_user_email_is_invalid(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        # Simulate dirty existing data bypassing User.save()/form validation.
        User.objects.filter(pk=user.pk).update(email="not-an-email")

        with self.assertRaises(ValidationError):
            sync_primary_email_address_for_user(user_id=user.id)

        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

    def test_blank_email_is_rejected_by_database_before_service_can_run(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(pk=user.pk).update(email="")


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
