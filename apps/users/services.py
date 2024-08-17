from django.contrib.auth.models import User
from django.db.models import Count
from django.db.models.query import QuerySet

from users.models import Profile


def create_user_profile(user: User) -> Profile:
    profile = Profile.objects.create(user=user)
    return profile


def get_user_by_id(user_id: int) -> User:
    return User.objects.get(id=user_id)


def find_user_profiles_with_subscribers() -> QuerySet[Profile]:
    """Returns a queryset of profiles belonging to users that have at
    least 1 subscriber.
    """
    return Profile.objects.annotate(subscribers_count=Count("subscribers")).filter(
        subscribers_count__gt=0
    )


def get_all_supscriptions_of_user(user: User) -> list[str]:
    """Returns a list of usernames of all authors the specified user is
    subscribed to.
    """
    return [p.user.username for p in user.subscribed_profiles.all()]
