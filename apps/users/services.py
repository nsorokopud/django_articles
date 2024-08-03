from django.contrib.auth.models import User

from users.models import Profile


def create_user_profile(user: User) -> Profile:
    profile = Profile.objects.create(user=user)
    return profile


def get_user_by_id(user_id: int) -> User:
    return User.objects.get(id=user_id)
