from django.contrib import admin
from django.test import RequestFactory, TestCase

from users.admin import PendingEmailChangeAdmin, UserProfileAdmin
from users.models import DEFAULT_PROFILE_IMAGE, PendingEmailChange, Profile, User


class TestCustomUserAdmin(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.user_admin = admin.site._registry[User]

    def test_email_is_not_readonly_when_creating_user(self):
        readonly_fields = self.user_admin.get_readonly_fields(
            request=self.request, obj=None
        )

        self.assertNotIn("email", readonly_fields)
        self.assertIn("unread_notifications_count", readonly_fields)

    def test_email_is_readonly_when_editing_existing_user(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        readonly_fields = self.user_admin.get_readonly_fields(
            request=self.request, obj=user
        )

        self.assertIn("email", readonly_fields)
        self.assertIn("unread_notifications_count", readonly_fields)

    def test_email_is_not_duplicated_in_readonly_fields(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        readonly_fields = self.user_admin.get_readonly_fields(
            request=self.request, obj=user
        )

        self.assertEqual(readonly_fields.count("email"), 1)


class TestUserProfileAdmin(TestCase):
    def setUp(self):
        self.profile_admin = UserProfileAdmin(Profile, admin.site)

    def test_get_profile_image_returns_dash_without_image(self):
        profile = Profile(image="")

        self.assertEqual(self.profile_admin.get_profile_image(profile), "-")

    def test_get_profile_image_returns_image_tag(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)
        profile.image = DEFAULT_PROFILE_IMAGE

        html = self.profile_admin.get_profile_image(profile)

        self.assertIn("<img", html)
        self.assertIn("width='35'", html)
        self.assertIn("height='35'", html)
        self.assertIn(DEFAULT_PROFILE_IMAGE, html)


class TestPendingEmailChangeAdmin(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/users/pendingemailchange/")

    def test_is_registered_with_custom_admin(self):
        pending_email_change_admin = admin.site._registry[PendingEmailChange]

        self.assertIsInstance(pending_email_change_admin, PendingEmailChangeAdmin)

    def test_disallows_manual_creation(self):
        pending_email_change_admin = admin.site._registry[PendingEmailChange]

        self.assertFalse(pending_email_change_admin.has_add_permission(self.request))

    def test_has_expected_readonly_fields(self):
        pending_email_change_admin = admin.site._registry[PendingEmailChange]

        self.assertEqual(
            pending_email_change_admin.readonly_fields, ("user", "email", "created_at")
        )
