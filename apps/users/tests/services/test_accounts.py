from django.core.exceptions import ValidationError
from django.test import TestCase

from users.models import PendingEmailChange, User
from users.services.accounts import activate_user, register_user


class TestRegisterUser(TestCase):
    def test_creates_inactive_user(self):
        user = register_user(
            username="newuser", email="NEW@TEST.COM", password="testpass123"
        )

        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.email, "new@test.com")
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password("testpass123"))

    def test_strips_username_and_email(self):
        user = register_user(
            username="  newuser  ", email="  NEW@TEST.COM  ", password="testpass123"
        )

        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.email, "new@test.com")

    def test_allows_email_used_by_pending_email_change(self):
        existing_user = User.objects.create_user(
            username="existing", email="existing@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=existing_user, email="pending@test.com"
        )

        user = register_user(
            username="newuser", email="PENDING@TEST.COM", password="testpass123"
        )

        self.assertEqual(user.email, "pending@test.com")
        self.assertFalse(user.is_active)
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_rejects_blank_username(self):
        with self.assertRaises(ValidationError) as context:
            register_user(username="   ", email="new@test.com", password="testpass123")

        self.assertEqual(
            context.exception.message_dict, {"username": ["Username is required."]}
        )

    def test_rejects_email_like_username(self):
        with self.assertRaises(ValidationError) as context:
            register_user(
                username="newuser@test.com",
                email="new@test.com",
                password="testpass123",
            )

        self.assertEqual(
            context.exception.messages, ["Username cannot be an email address."]
        )

    def test_rejects_email_like_username_after_trimming(self):
        with self.assertRaises(ValidationError) as context:
            register_user(
                username="  newuser@test.com  ",
                email="new@test.com",
                password="testpass123",
            )

        self.assertEqual(
            context.exception.messages, ["Username cannot be an email address."]
        )

    def test_rejects_existing_username_case_insensitively_after_trimming(self):
        User.objects.create_user(
            username="Max", email="max1@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="  max  ", email="max2@test.com", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"username": ["A user with that username already exists."]},
        )

    def test_rejects_blank_email(self):
        with self.assertRaises(ValidationError) as context:
            register_user(username="newuser", email="   ", password="testpass123")

        self.assertEqual(
            context.exception.message_dict, {"email": ["Email is required."]}
        )

    def test_rejects_invalid_email(self):
        with self.assertRaises(ValidationError):
            register_user(
                username="newuser", email="not-an-email", password="testpass123"
            )

    def test_rejects_existing_email_case_insensitively(self):
        User.objects.create_user(
            username="existing", email="taken@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="newuser", email="TAKEN@TEST.COM", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"email": ["A user with that email already exists."]},
        )

    def test_rejects_existing_email_after_trimming(self):
        User.objects.create_user(
            username="existing", email="taken@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="newuser", email="  TAKEN@TEST.COM  ", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"email": ["A user with that email already exists."]},
        )

    def test_rejects_existing_username(self):
        User.objects.create_user(
            username="taken", email="taken@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="taken", email="new@test.com", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"username": ["A user with that username already exists."]},
        )

    def test_rejects_existing_username_after_trimming(self):
        User.objects.create_user(
            username="taken", email="taken@test.com", password="testpass123"
        )

        with self.assertRaises(ValidationError) as context:
            register_user(
                username="  taken  ", email="new@test.com", password="testpass123"
            )

        self.assertEqual(
            context.exception.message_dict,
            {"username": ["A user with that username already exists."]},
        )


class TestActivateUser(TestCase):
    def test_activates_user(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

        self.assertFalse(user.is_active)

        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)

    def test_is_idempotent(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

        activate_user(user)
        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)

    def test_keeps_user_active_when_already_active(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=True
        )

        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)

    def test_does_not_modify_email(self):
        user = User.objects.create_user(
            username="user", email="User@Test.COM", is_active=False
        )

        activate_user(user)
        user.refresh_from_db()

        self.assertEqual(user.email, "user@test.com")
        self.assertTrue(user.is_active)

    def test_does_not_delete_matching_pending_email_change_when_user_activates(self):
        existing_user = User.objects.create_user(
            username="existing", email="existing@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=existing_user, email="user@test.com"
        )

        user = User.objects.create_user(
            username="user", email="USER@TEST.COM", is_active=False
        )

        activate_user(user)

        user.refresh_from_db()

        self.assertTrue(user.is_active)
        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_does_not_delete_unrelated_pending_email_change_when_user_activates(self):
        existing_user = User.objects.create_user(
            username="existing", email="existing@test.com", password="testpass123"
        )
        unrelated_pending_email_change = PendingEmailChange.objects.create(
            user=existing_user, email="other@test.com"
        )

        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

        activate_user(user)

        self.assertTrue(
            PendingEmailChange.objects.filter(
                pk=unrelated_pending_email_change.pk
            ).exists()
        )
