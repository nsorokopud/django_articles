from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ValidationError
from django.test import TestCase

from users.models import User
from users.services import (
    change_email_address,
    create_pending_email_address,
    delete_pending_email_address,
    enforce_unique_email_type_per_user,
)


class TestEmailAddressServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def test_create_pending_email_address(self):
        self.assertEqual(
            EmailAddress.objects.filter(
                user=self.test_user, primary=False, verified=False
            ).count(),
            0,
        )
        create_pending_email_address(self.test_user, email="new@test.com")
        self.assertEqual(
            EmailAddress.objects.get(
                user=self.test_user, primary=False, verified=False
            ).email,
            "new@test.com",
        )

    def test_delete_pending_email_address(self):
        self.assertEqual(EmailAddress.objects.count(), 0)
        delete_pending_email_address(self.test_user)

        email = EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        self.assertEqual(EmailAddress.objects.count(), 1)
        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = False
        email.save()
        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = True
        email.verified = False
        email.save()
        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = False
        email.save()
        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 0)

    def test_change_email_address(self):
        email1 = EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        email2 = EmailAddress.objects.create(
            user=self.test_user, email="e2@test.com", primary=False, verified=True
        )
        SocialAccount.objects.create(
            user=self.test_user,
            provider="p1",
            uid="123",
            extra_data={"email": email1.email},
        )
        self.assertEqual(SocialAccount.objects.count(), 1)

        with self.assertRaises(EmailAddress.DoesNotExist):
            change_email_address(self.test_user.id)

        email2.verified = False
        email2.save(update_fields=["verified"])

        change_email_address(self.test_user.id)
        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, email2.email)

        email2.refresh_from_db()
        self.assertTrue(email2.primary)
        self.assertTrue(email2.verified)

        with self.assertRaises(EmailAddress.DoesNotExist):
            EmailAddress.objects.get(pk=email1.pk)

        self.assertEqual(SocialAccount.objects.count(), 0)


class TestEnforceUniqueEmailTypePerUser(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="test@test.com")

    def test_one_primary_email_allowed(self):
        EmailAddress.objects.create(
            user=self.user, email="test1@test.com", primary=True
        )
        email2 = EmailAddress(user=self.user, email="test2@test.com", primary=False)
        enforce_unique_email_type_per_user(email2)

        email2.save()
        email3 = EmailAddress(user=self.user, email="test3@test.com", primary=False)
        with self.assertRaises(ValidationError) as context:
            enforce_unique_email_type_per_user(email3)
            self.assertEqual(
                str(context.exception),
                "['This user already has a primary email address.']",
            )

    def test_one_non_primary_email_allowed(self):
        EmailAddress.objects.create(
            user=self.user, email="test1@test.com", primary=False
        )
        email2 = EmailAddress(user=self.user, email="test2@test.com", primary=True)
        enforce_unique_email_type_per_user(email2)

        email2.save()
        email3 = EmailAddress(user=self.user, email="test3@test.com", primary=True)
        with self.assertRaises(ValidationError) as context:
            enforce_unique_email_type_per_user(email3)
            self.assertEqual(
                str(context.exception),
                "['This user already has a primary email address.']",
            )

    def test_many_unsaved_instances_allowed(self):
        email1 = EmailAddress(user=self.user, email="e1@test.com", primary=True)
        email2 = EmailAddress(user=self.user, email="e2@test.com", primary=True)
        email3 = EmailAddress(user=self.user, email="e3@test.com", primary=True)
        enforce_unique_email_type_per_user(email1)
        enforce_unique_email_type_per_user(email2)
        enforce_unique_email_type_per_user(email3)

        email4 = EmailAddress(user=self.user, email="e4@test.com", primary=False)
        email5 = EmailAddress(user=self.user, email="e5@test.com", primary=False)
        email6 = EmailAddress(user=self.user, email="e6@test.com", primary=False)
        enforce_unique_email_type_per_user(email4)
        enforce_unique_email_type_per_user(email5)
        enforce_unique_email_type_per_user(email6)
