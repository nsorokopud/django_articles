from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.test import TestCase

from users.models import Profile, User


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
    @patch("users.signals.enforce_single_current_and_pending_email_per_user")
    def test_enforce_single_current_and_pending_email_per_user_called(
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
            "['This user already has a pending email address.']",
        )
