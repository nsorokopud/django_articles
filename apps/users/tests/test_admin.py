from allauth.account.models import EmailAddress
from django.contrib import admin
from django.test import RequestFactory, TestCase

from users.admin import EmailAddressAdmin, UserProfileAdmin
from users.forms import EmailAddressModelForm
from users.models import DEFAULT_PROFILE_IMAGE, Profile, User


class TestCustomUserAdmin(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.user_admin = admin.site._registry[User]

    def test_email_is_not_readonly_when_creating_user(self):
        readonly_fields = self.user_admin.get_readonly_fields(
            request=self.request, obj=None
        )

        self.assertNotIn("email", readonly_fields)
        self.assertIn("latest_article_publish_sequence", readonly_fields)
        self.assertIn("subscriptions_last_seen_publish_sequence", readonly_fields)
        self.assertIn("unread_notifications_count", readonly_fields)

    def test_email_is_readonly_when_editing_existing_user(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        readonly_fields = self.user_admin.get_readonly_fields(
            request=self.request, obj=user
        )

        self.assertIn("email", readonly_fields)
        self.assertIn("latest_article_publish_sequence", readonly_fields)
        self.assertIn("subscriptions_last_seen_publish_sequence", readonly_fields)
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


class TestEmailAddressAdmin(TestCase):
    def test_email_address_admin_uses_custom_form(self):
        email_admin = admin.site._registry[EmailAddress]

        self.assertIsInstance(email_admin, EmailAddressAdmin)
        self.assertIs(email_admin.form, EmailAddressModelForm)
