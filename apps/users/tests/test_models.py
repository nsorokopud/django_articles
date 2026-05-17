from contextlib import contextmanager

from allauth.account.models import EmailAddress
from django.db import IntegrityError, transaction
from django.db.models.signals import pre_save
from django.test import TestCase

from users.models import (
    DEFAULT_PROFILE_IMAGE,
    AuthorSubscription,
    Profile,
    TokenCounter,
    TokenType,
    User,
    profile_image_upload_path,
)
from users.signals import enforce_email_address_validation_rules


@contextmanager
def email_address_model_validation_disabled():
    """Temporarily disable the EmailAddress pre_save validation signal so tests can
    assert the actual database constraints raise IntegrityError.

    Keep this scoped to individual tests/blocks so other tests still exercise
    normal application behavior.
    """
    pre_save.disconnect(enforce_email_address_validation_rules, sender=EmailAddress)
    try:
        yield
    finally:
        # Avoid duplicate receiver registration if something reconnected it
        pre_save.disconnect(enforce_email_address_validation_rules, sender=EmailAddress)
        pre_save.connect(enforce_email_address_validation_rules, sender=EmailAddress)


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
                User.objects.create_user(
                    username="user2", email=" user@test.com ", password="testpass123"
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


class TestEmailAddressConstraints(TestCase):
    def test_email_address_email_is_case_insensitive_unique(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="testpass123"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            EmailAddress.objects.create(
                user=user1, email="same@test.com", verified=True, primary=True
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    EmailAddress.objects.create(
                        user=user2, email="SAME@test.com", verified=True, primary=False
                    )

    def test_email_address_email_unique_constraint_trims_whitespace(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="testpass123"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            EmailAddress.objects.create(
                user=user1, email="same@test.com", verified=True, primary=True
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    EmailAddress.objects.create(
                        user=user2,
                        email=" same@test.com ",
                        verified=True,
                        primary=False,
                    )

    def test_email_address_email_is_unique_even_for_same_user(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            EmailAddress.objects.create(
                user=user, email="same@test.com", verified=True, primary=True
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    EmailAddress.objects.create(
                        user=user, email="SAME@test.com", verified=False, primary=False
                    )

    def test_user_cannot_have_multiple_primary_email_addresses(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            EmailAddress.objects.create(
                user=user, email="primary1@test.com", verified=True, primary=True
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    EmailAddress.objects.create(
                        user=user,
                        email="primary2@test.com",
                        verified=True,
                        primary=True,
                    )

    def test_user_cannot_have_multiple_nonprimary_email_addresses(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            EmailAddress.objects.create(
                user=user, email="secondary1@test.com", verified=True, primary=False
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    EmailAddress.objects.create(
                        user=user,
                        email="secondary2@test.com",
                        verified=False,
                        primary=False,
                    )

    def test_user_cannot_have_multiple_unverified_nonprimary_email_addresses(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            EmailAddress.objects.create(
                user=user, email="pending1@test.com", verified=False, primary=False
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    EmailAddress.objects.create(
                        user=user,
                        email="pending2@test.com",
                        verified=False,
                        primary=False,
                    )

    def test_user_can_have_primary_and_one_nonprimary_email_address(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            primary_email = EmailAddress.objects.create(
                user=user, email="current@test.com", verified=True, primary=True
            )
            nonprimary_email = EmailAddress.objects.create(
                user=user, email="pending@test.com", verified=False, primary=False
            )

        self.assertEqual(primary_email.email, "current@test.com")
        self.assertEqual(nonprimary_email.email, "pending@test.com")

    def test_different_users_can_each_have_one_nonprimary_email_address(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="testpass123"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="testpass123"
        )

        with email_address_model_validation_disabled():
            EmailAddress.objects.create(
                user=user1, email="pending1@test.com", verified=False, primary=False
            )
            email2 = EmailAddress.objects.create(
                user=user2, email="pending2@test.com", verified=False, primary=False
            )

        self.assertEqual(email2.email, "pending2@test.com")


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

        self.assertTrue(path.startswith(f"users/profile_images/{user.id}/My_Avatar_"))
        self.assertTrue(path.endswith(".jpg"))

    def test_profile_image_upload_path_sanitizes_filename(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "../../...///bad file name.PNG")

        self.assertTrue(
            path.startswith(f"users/profile_images/{user.id}/bad_file_name_")
        )
        self.assertTrue(path.endswith(".png"))
        self.assertNotIn("..", path)

    def test_profile_image_upload_path_uses_avatar_when_base_name_is_empty(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )
        profile = Profile.objects.get(user=user)

        path = profile_image_upload_path(profile, "...")

        self.assertTrue(path.startswith(f"users/profile_images/{user.id}/avatar_"))

    def test_profile_image_upload_path_requires_user_id(self):
        profile = Profile()

        with self.assertRaisesMessage(
            ValueError, "user_id is required to upload profile images"
        ):
            profile_image_upload_path(profile, "avatar.jpg")


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
        self.assertTrue(subscription.notifications_enabled)

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


class TestTokenCounterModel(TestCase):
    def test_token_counter_can_be_created(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        counter = TokenCounter.objects.create(
            user=user, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=1
        )

        self.assertEqual(counter.user, user)
        self.assertEqual(counter.token_type, TokenType.ACCOUNT_ACTIVATION)
        self.assertEqual(counter.token_count, 1)

    def test_token_counter_user_and_token_type_are_unique_together(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        TokenCounter.objects.create(
            user=user, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=1
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TokenCounter.objects.create(
                    user=user, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=2
                )

    def test_same_user_can_have_different_token_counter_types(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        TokenCounter.objects.create(
            user=user, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=1
        )
        counter = TokenCounter.objects.create(
            user=user, token_type=TokenType.EMAIL_CHANGE, token_count=1
        )

        self.assertEqual(counter.token_type, TokenType.EMAIL_CHANGE)

    def test_different_users_can_have_same_token_counter_type(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="testpass123"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="testpass123"
        )

        TokenCounter.objects.create(
            user=user1, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=1
        )
        counter2 = TokenCounter.objects.create(
            user=user2, token_type=TokenType.ACCOUNT_ACTIVATION, token_count=1
        )

        self.assertEqual(counter2.user, user2)

    def test_invalid_token_type_is_not_allowed(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TokenCounter.objects.create(
                    user=user, token_type="invalid", token_count=1
                )

    def test_token_counter_str(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123"
        )

        counter = TokenCounter.objects.create(
            user=user, token_type=TokenType.PASSWORD_CHANGE, token_count=3
        )

        self.assertEqual(
            str(counter), f"{user.username} - {TokenType.PASSWORD_CHANGE} - 3"
        )
