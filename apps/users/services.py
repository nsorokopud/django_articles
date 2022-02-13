from django.contrib.auth.models import User

from .models import Profile


def create_user_profile(user: User) -> Profile:
    profile = Profile.objects.create(user=user)
    return profile
