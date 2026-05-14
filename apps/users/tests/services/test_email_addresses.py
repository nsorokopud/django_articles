from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.test import TestCase

from users.models import User
from users.services import (
    change_email_address,
    create_pending_email_address,
    delete_pending_email_address,
    enforce_single_current_and_pending_email_per_user,
)


class TestEmailAddressServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def test_delete_pending_email_address(self):
        self.assertEqual(EmailAddress.objects.count(), 0)

        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 0)

        email = EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        self.assertEqual(EmailAddress.objects.count(), 1)

        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = False
        email.verified = True
        email.save(update_fields=["primary", "verified"])

        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = True
        email.verified = False
        email.save(update_fields=["primary", "verified"])

        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = False
        email.verified = False
        email.save(update_fields=["primary", "verified"])

        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 0)

    def test_change_email_address_requires_unverified_pending_email(self):
        EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        EmailAddress.objects.create(
            user=self.test_user, email="e2@test.com", primary=False, verified=True
        )

        with self.assertRaises(EmailAddress.DoesNotExist):
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
            ValidationError, "This user already has a pending email address."
        ):
            create_pending_email_address(user_id=self.user.id, email="new@test.com")

        self.assertFalse(
            EmailAddress.objects.filter(user=self.user, email="new@test.com").exists()
        )


class TestEnforceSingleCurrentAndPendingEmailPerUser(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="test@test.com")

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
        User.objects.create_user(username="other", email="taken@test.com")

        email = EmailAddress(
            user=self.user, email="TAKEN@TEST.COM", primary=False, verified=False
        )

        with self.assertRaises(ValidationError) as context:
            enforce_single_current_and_pending_email_per_user(email)

        self.assertEqual(
            context.exception.messages, ["A user with that email already exists."]
        )

    def test_rejects_email_used_by_another_users_email_address_case_insensitively(self):
        other_user = User.objects.create_user(username="other", email="other@test.com")
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
