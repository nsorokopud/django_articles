import os

from django.conf import settings
from django.contrib.auth.models import User

from .models import Profile


def create_user_profile(user: User) -> Profile:
    profile = Profile.objects.create(user=user)
    return profile


def delete_profile_image(image_name: str) -> None:
    os.remove(os.path.join(settings.MEDIA_ROOT, "users", "profile_images", image_name))
