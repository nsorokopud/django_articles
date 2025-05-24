from typing import Optional

from allauth.account.models import EmailAddress
from django.db.models import Count
from django.db.models.query import QuerySet

from users.models import Profile, User


def get_all_users() -> QuerySet[User]:
    return User.objects.all()


def get_user_by_id(user_id: int) -> User:
    return User.objects.get(id=user_id)


def get_user_by_username(username: str) -> User:
    return User.objects.get(username=username)


def find_user_profiles_with_subscribers() -> QuerySet[Profile]:
    """Returns a queryset of profiles belonging to users that have at
    least 1 subscriber.
    """
    return Profile.objects.annotate(subscribers_count=Count("subscribers")).filter(
        subscribers_count__gt=0
    )


def get_all_subscriptions_of_user(user: User) -> QuerySet[tuple[int, str]]:
    """Returns a QuerySet of (user_id, username) tuples for all authors
    the specified user is subscribed to.
    """
    return user.subscribed_profiles.values_list("user__id", "user__username")


def get_pending_email_address(user: User) -> Optional[EmailAddress]:
    try:
        return EmailAddress.objects.get(user=user, primary=False, verified=False)
    except EmailAddress.DoesNotExist:
        return None
