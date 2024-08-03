from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TestCase

from users.models import Profile
from users.services import create_user_profile, find_user_profiles_with_subscribers, get_user_by_id
from users.signals import create_profile


class TestServices(TestCase):
    def setUp(self):
        signals.post_save.disconnect(create_profile, sender=User)

        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()
        self.test_profile = Profile.objects.create(user=self.test_user)

    def test_create_user_profile(self):
        with self.assertRaises(Profile.DoesNotExist):
            profile = Profile.objects.get(user=self.test_user)
        profile = create_user_profile(self.test_user)
        self.assertEqual(profile.user, self.test_user)
        self.assertEqual(Profile.objects.filter(user=self.test_user).first(), profile)

    def test_get_user_by_id(self):
        u1 = get_user_by_id(self.test_user.id)
        self.assertEqual(u1, self.test_user)

        u1_id = u1.id
        next_user_id = u1_id + 1
        with self.assertRaises(User.DoesNotExist):
            get_user_by_id(next_user_id)

        u2 = User.objects.create(username="user2", email="test2@test.com")
        next_user = get_user_by_id(next_user_id)
        self.assertEqual(next_user, u2)

        with self.assertRaises(User.DoesNotExist):
            get_user_by_id(999)

    def test_find_user_profiles_with_subscribers(self):
        signals.post_save.disconnect(create_profile, sender=User)

        u1 = User.objects.create(username="user1", email="test1@test.com")
        u2 = User.objects.create(username="user2", email="test2@test.com")

        p0 = self.test_user.profile
        p1 = Profile.objects.create(user=u1)
        p2 = Profile.objects.create(user=u2)

        self.assertCountEqual(find_user_profiles_with_subscribers(), [])

        p0.subscribers.add(*[u1, u2])
        self.assertCountEqual(find_user_profiles_with_subscribers(), [p0])

        p1.subscribers.add(u2)
        self.assertCountEqual(find_user_profiles_with_subscribers(), [p0, p1])

        p1.subscribers.remove(u2)
        self.assertCountEqual(find_user_profiles_with_subscribers(), [p0])

        p0.subscribers.remove(*[u1, u2])
        self.assertCountEqual(find_user_profiles_with_subscribers(), [])
