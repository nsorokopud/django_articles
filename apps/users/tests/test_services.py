from django.db.models import signals
from django.contrib.auth.models import User
from django.test import TestCase

from users.models import Profile
from users.services import create_user_profile
from users.signals import create_profile


class TestServices(TestCase):
    def setUp(self):
        signals.post_save.disconnect(create_profile, sender=User)

        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()

    def test_create_user_profile(self):
        with self.assertRaises(Profile.DoesNotExist):
            profile = Profile.objects.get(user=self.test_user)
        profile = create_user_profile(self.test_user)
        self.assertEquals(profile.user, self.test_user)
        self.assertEquals(Profile.objects.filter(user=self.test_user).first(), profile)
