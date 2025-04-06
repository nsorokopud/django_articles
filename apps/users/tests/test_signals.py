from django.test import TestCase

from users.models import Profile, User


class TestSignals(TestCase):
    def test_profile_created_when_user_created(self):
        u1 = User.objects.create(username="user1", email="email1@example.com")
        p1 = Profile.objects.get(user__id=u1.id)
        self.assertEqual(p1.user.username, u1.username)
        self.assertEqual(Profile.objects.count(), 1)

        u2 = User.objects.create(username="user2", email="email2@example.com")
        p2 = Profile.objects.get(user__id=u2.id)
        self.assertEqual(p2.user.username, u2.username)
        self.assertEqual(Profile.objects.count(), 2)
