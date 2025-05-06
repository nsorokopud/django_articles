from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.test import TestCase

from users.models import Profile, User
from users.signals import enforce_email_address_validation_rules


class TestCreateProfile(TestCase):
    def test(self):
        u1 = User.objects.create(username="user1", email="email1@example.com")
        p1 = Profile.objects.get(user__id=u1.id)
        self.assertEqual(p1.user.username, u1.username)
        self.assertEqual(Profile.objects.count(), 1)

        u2 = User.objects.create(username="user2", email="email2@example.com")
        p2 = Profile.objects.get(user__id=u2.id)
        self.assertEqual(p2.user.username, u2.username)
        self.assertEqual(Profile.objects.count(), 2)


class TestEnforceEmailAddressValidationRules(TestCase):
    @patch("users.signals.enforce_unique_email_type_per_user")
    def test_enforce_unique_email_type_per_user_called(
        self, mock_validate_email_address
    ):
        user = User.objects.create_user(username="user1", email="user@test.com")
        email = EmailAddress.objects.create(user=user, email=user.email)
        mock_validate_email_address.assert_called_once_with(email)

    def test_validation_error_raised(self):
        user = User.objects.create(username="user", email="user@test.com")
        EmailAddress.objects.create(user=user, email="e1@test.com", primary=False)
        email2 = EmailAddress(user=user, email="e2@test.com", primary=False)

        with self.assertRaises(ValidationError) as context:
            email2.save()
        self.assertEqual(
            str(context.exception),
            "['This user already has a non-primary email address.']",
        )

        pre_save.disconnect(enforce_email_address_validation_rules, sender=EmailAddress)
        email2.save()
        pre_save.connect(enforce_email_address_validation_rules, sender=EmailAddress)
