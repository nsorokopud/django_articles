from uuid import UUID

from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from users.models import (
    DEFAULT_PROFILE_IMAGE,
    PROFILE_IMAGE_EXTENSION_MAX_LENGTH,
    PROFILE_IMAGE_MAX_LENGTH,
    PROFILE_IMAGE_UPLOAD_PREFIX,
    PROFILE_IMAGE_UUID_LENGTH,
    AuthorSubscription,
    PendingEmailChange,
    Profile,
    User,
    profile_image_upload_path,
)


class TestUserModel(TestCase):
    def test_email_is_lowercased_on_create(self):
        user = User.objects.create_user(
            username="user", email="User.Test@Test.COM", password="testpass123"
        )
        user.refresh_from_db()

        self.assertEqual(user.email, "user.test@test.com")

    def test_email_is_trimmed_on_create(self):
        user = User.objects.create_user(
            username="user", email="  User.Test@Test.COM  ", password="testpass123"
        )
        user.refresh_from_db()

        self.assertEqual(user.email, "user.test@test.com")

    def test_email_is_lowercased_on_save(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        user.email = "New.Email@Test.COM"
        user.save(update_fields=["email"])
        user.refresh_from_db()

        self.assertEqual(user.email, "new.email@test.com")

    def test_email_is_trimmed_on_save(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        user.email = "  New.Email@Test.COM  "
        user.save(update_fields=["email"])
        user.refresh_from_db()

        self.assertEqual(user.email, "new.email@test.com")

    def test_email_case_insensitive_unique_constraint(self):
        User.objects.create_user(
            username="user1", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="user2", email="USER@test.com", password="testpass123"
                )

    def test_email_unique_constraint_trims_whitespace(self):
        User.objects.create_user(
            username="user1", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.bulk_create(
                    [User(username="user2", email=" user@test.com ")]
                )

    def test_email_cannot_be_blank(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="user", email="", password="testpass123"
                )

    def test_email_cannot_be_whitespace_only(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="user", email="   ", password="testpass123"
                )

    def test_username_is_trimmed_on_create(self):
        user = User.objects.create_user(
            username="  user  ", email="user@test.com", password="testpass123"
        )
        user.refresh_from_db()

        self.assertEqual(user.username, "user")

    def test_username_is_trimmed_on_save(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        user.username = "  new_user  "
        user.save(update_fields=["username"])
        user.refresh_from_db()

        self.assertEqual(user.username, "new_user")

    def test_username_cannot_contain_at_symbol_on_save(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        user.username = "user@test.com"

        with self.assertRaises(ValidationError):
            user.save(update_fields=["username"])

    def test_username_cannot_contain_at_symbol_at_database_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.bulk_create(
                    [User(username="user@test.com", email="user@test.com")]
                )

    def test_username_case_insensitive_unique_constraint(self):
        User.objects.create_user(
            username="Max", email="max1@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="max", email="max2@test.com", password="testpass123"
                )

    def test_username_unique_constraint_trims_whitespace(self):
        User.objects.create_user(
            username="Max", email="max1@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.bulk_create(
                    [User(username=" max ", email="max2@test.com")]
                )

    def test_username_exact_unique_constraint(self):
        User.objects.create_user(
            username="Max", email="max1@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="Max", email="max2@test.com", password="testpass123"
                )

    def test_session_auth_hash_changes_when_session_auth_version_changes(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        original_hash = user.get_session_auth_hash()

        user.session_auth_version += 1
        user.save(update_fields=["session_auth_version"])

        user.refresh_from_db()
        self.assertNotEqual(original_hash, user.get_session_auth_hash())

    def test_user_delete_deletes_allauth_email_addresses(self):
        user = User.objects.create_user(username="user", email="test@test.com")
        email_address = EmailAddress.objects.create(
            user=user, email="test@test.com", verified=True, primary=True
        )

        user.delete()

        self.assertFalse(EmailAddress.objects.filter(pk=email_address.pk).exists())


class TestPendingEmailChangeModel(TestCase):
    def test_pending_email_change_can_be_created(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        pending_email_change = PendingEmailChange.objects.create(
            user=user, email="new@test.com"
        )

        self.assertEqual(pending_email_change.user, user)
        self.assertEqual(pending_email_change.email, "new@test.com")
        self.assertIsNotNone(pending_email_change.created_at)

    def test_pending_email_change_public_id_is_uuid4(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        pending = PendingEmailChange.objects.create(user=user, email="new@test.com")

        self.assertIsInstance(pending.public_id, UUID)
        self.assertEqual(pending.public_id.version, 4)

    def test_pending_email_change_public_id_defaults_to_unique_value_per_row(self):
        user1 = User.objects.create_user(username="user1", email="user1@test.com")
        user2 = User.objects.create_user(username="user2", email="user2@test.com")

        pending1 = PendingEmailChange.objects.create(user=user1, email="new1@test.com")
        pending2 = PendingEmailChange.objects.create(user=user2, email="new2@test.com")

        self.assertNotEqual(pending1.public_id, pending2.public_id)

    def test_pending_email_change_email_is_lowercased_on_create(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        pending_email_change = PendingEmailChange.objects.create(
            user=user, email="New.Email@Test.COM"
        )
        pending_email_change.refresh_from_db()

        self.assertEqual(pending_email_change.email, "new.email@test.com")

    def test_pending_email_change_email_is_trimmed_on_create(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        pending_email_change = PendingEmailChange.objects.create(
            user=user, email="  New.Email@Test.COM  "
        )
        pending_email_change.refresh_from_db()

        self.assertEqual(pending_email_change.email, "new.email@test.com")

    def test_pending_email_change_email_is_lowercased_on_save(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=user, email="old@test.com"
        )

        pending_email_change.email = "New.Email@Test.COM"
        pending_email_change.save(update_fields=["email"])
        pending_email_change.refresh_from_db()

        self.assertEqual(pending_email_change.email, "new.email@test.com")

    def test_pending_email_change_email_is_trimmed_on_save(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=user, email="old@test.com"
        )

        pending_email_change.email = "  New.Email@Test.COM  "
        pending_email_change.save(update_fields=["email"])
        pending_email_change.refresh_from_db()

        self.assertEqual(pending_email_change.email, "new.email@test.com")

    def test_user_can_have_only_one_pending_email_change(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        PendingEmailChange.objects.create(user=user, email="new1@test.com")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(user=user, email="new2@test.com")

    def test_different_users_can_have_pending_email_changes(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="testpass123"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="testpass123"
        )

        PendingEmailChange.objects.create(user=user1, email="new1@test.com")
        pending_email_change2 = PendingEmailChange.objects.create(
            user=user2, email="new2@test.com"
        )

        self.assertEqual(pending_email_change2.user, user2)
        self.assertEqual(pending_email_change2.email, "new2@test.com")

    def test_pending_email_change_email_is_case_insensitive_unique(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="testpass123"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="testpass123"
        )

        PendingEmailChange.objects.create(user=user1, email="same@test.com")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(user=user2, email="SAME@test.com")

    def test_pending_email_change_email_unique_constraint_trims_whitespace(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="testpass123"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="testpass123"
        )

        PendingEmailChange.objects.create(user=user1, email="same@test.com")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(user=user2, email=" same@test.com ")

    def test_pending_email_change_email_cannot_be_blank(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(user=user, email="")

    def test_pending_email_change_email_cannot_be_whitespace_only(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingEmailChange.objects.create(user=user, email="   ")

    def test_pending_email_change_is_deleted_when_user_is_deleted(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=user, email="new@test.com"
        )

        user.delete()

        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

    def test_pending_email_change_str(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        pending_email_change = PendingEmailChange.objects.create(
            user=user, email="new@test.com"
        )

        self.assertEqual(str(pending_email_change), "new@test.com")


class TestProfileModel(TestCase):
    def test_profile_is_created_when_user_is_created(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_uses_default_image(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        self.assertEqual(profile.image.name, DEFAULT_PROFILE_IMAGE)

    def test_profile_str(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        self.assertEqual(str(profile), "user's profile")

    def test_profile_image_upload_path_uses_user_id(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "My Avatar.JPG")

        self.assertTrue(
            path.startswith(f"{PROFILE_IMAGE_UPLOAD_PREFIX}/{user.id}/My_Avatar_")
        )
        self.assertTrue(path.endswith(".jpg"))
        self.assertLessEqual(len(path), PROFILE_IMAGE_MAX_LENGTH)

    def test_profile_image_upload_path_sanitizes_filename(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "../../...///bad file name.PNG")

        self.assertTrue(
            path.startswith(f"{PROFILE_IMAGE_UPLOAD_PREFIX}/{user.id}/bad_file_name_")
        )
        self.assertTrue(path.endswith(".png"))
        self.assertNotIn("..", path)
        self.assertLessEqual(len(path), PROFILE_IMAGE_MAX_LENGTH)

    def test_profile_image_upload_path_uses_avatar_when_base_name_is_empty(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "...")

        self.assertTrue(
            path.startswith(f"{PROFILE_IMAGE_UPLOAD_PREFIX}/{user.id}/avatar_")
        )
        self.assertLessEqual(len(path), PROFILE_IMAGE_MAX_LENGTH)

    def test_profile_image_upload_path_requires_user_id(self):
        profile = Profile()

        with self.assertRaisesMessage(
            ValueError, "user_id is required to upload profile images"
        ):
            profile_image_upload_path(profile, "avatar.jpg")

    def test_profile_image_upload_path_caps_total_length(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        very_long_base_name = "a" * 1000
        path = profile_image_upload_path(profile, f"{very_long_base_name}.jpg")

        self.assertLessEqual(len(path), PROFILE_IMAGE_MAX_LENGTH)
        self.assertTrue(path.startswith(f"{PROFILE_IMAGE_UPLOAD_PREFIX}/{user.id}/"))
        self.assertTrue(path.endswith(".jpg"))

    def test_profile_image_upload_path_caps_extension_length(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        long_extension = "a" * (PROFILE_IMAGE_EXTENSION_MAX_LENGTH + 20)
        path = profile_image_upload_path(profile, f"avatar.{long_extension}")

        extension = path.rsplit(".", 1)[1]

        self.assertEqual(len(extension), PROFILE_IMAGE_EXTENSION_MAX_LENGTH)
        self.assertLessEqual(len(path), PROFILE_IMAGE_MAX_LENGTH)

    def test_profile_image_upload_path_preserves_uuid_suffix_length(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "avatar.jpg")
        filename = path.rsplit("/", 1)[1]
        stem = filename.rsplit(".", 1)[0]
        suffix = stem.rsplit("_", 1)[1]

        self.assertEqual(len(suffix), PROFILE_IMAGE_UUID_LENGTH)
        self.assertRegex(suffix, r"^[0-9a-f]+$")

    def test_profile_image_field_max_length_matches_upload_path_limit(self):
        field = Profile._meta.get_field("image")

        self.assertEqual(field.max_length, PROFILE_IMAGE_MAX_LENGTH)


class TestAuthorSubscriptionModel(TestCase):
    def test_user_can_subscribe_to_author(self):
        subscriber = User.objects.create_user(
            username="subscriber", email="subscriber@test.com", password="testpass123"
        )
        author = User.objects.create_user(
            username="author", email="author@test.com", password="testpass123"
        )

        subscription = AuthorSubscription.objects.create(
            subscriber=subscriber, author=author
        )

        self.assertEqual(subscription.subscriber, subscriber)
        self.assertEqual(subscription.author, author)

    def test_user_cannot_subscribe_to_self(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AuthorSubscription.objects.create(subscriber=user, author=user)

    def test_duplicate_subscription_is_not_allowed(self):
        subscriber = User.objects.create_user(
            username="subscriber", email="subscriber@test.com", password="testpass123"
        )
        author = User.objects.create_user(
            username="author", email="author@test.com", password="testpass123"
        )

        AuthorSubscription.objects.create(subscriber=subscriber, author=author)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AuthorSubscription.objects.create(subscriber=subscriber, author=author)

    def test_same_subscriber_can_subscribe_to_different_authors(self):
        subscriber = User.objects.create_user(
            username="subscriber", email="subscriber@test.com", password="testpass123"
        )
        author1 = User.objects.create_user(
            username="author1", email="author1@test.com", password="testpass123"
        )
        author2 = User.objects.create_user(
            username="author2", email="author2@test.com", password="testpass123"
        )

        AuthorSubscription.objects.create(subscriber=subscriber, author=author1)
        subscription2 = AuthorSubscription.objects.create(
            subscriber=subscriber, author=author2
        )

        self.assertEqual(subscription2.author, author2)

    def test_different_subscribers_can_subscribe_to_same_author(self):
        subscriber1 = User.objects.create_user(
            username="subscriber1", email="subscriber1@test.com", password="testpass123"
        )
        subscriber2 = User.objects.create_user(
            username="subscriber2", email="subscriber2@test.com", password="testpass123"
        )
        author = User.objects.create_user(
            username="author", email="author@test.com", password="testpass123"
        )

        AuthorSubscription.objects.create(subscriber=subscriber1, author=author)
        subscription2 = AuthorSubscription.objects.create(
            subscriber=subscriber2, author=author
        )

        self.assertEqual(subscription2.subscriber, subscriber2)

    def test_author_subscription_str(self):
        subscriber = User.objects.create_user(
            username="subscriber", email="subscriber@test.com", password="testpass123"
        )
        author = User.objects.create_user(
            username="author", email="author@test.com", password="testpass123"
        )

        subscription = AuthorSubscription.objects.create(
            subscriber=subscriber, author=author
        )

        self.assertEqual(str(subscription), f"{subscriber.id} -> {author.id}")
