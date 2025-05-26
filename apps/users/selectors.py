from typing import Optional

from allauth.account.models import EmailAddress
from django.db.models.query import QuerySet

from users.models import User


def get_all_users() -> QuerySet[User]:
    return User.objects.all()


def get_user_by_id(user_id: int) -> User:
    return User.objects.get(id=user_id)


def get_all_subscriptions_of_user(user: User) -> QuerySet[tuple[int, str]]:
    """Returns a QuerySet of (user_id, username) tuples for all authors
    the specified user is subscribed to.
    """
    return user.subscribed_to_authors.values_list("id", "username")


def get_pending_email_address(user: User) -> Optional[EmailAddress]:
    try:
        return EmailAddress.objects.get(user=user, primary=False, verified=False)
    except EmailAddress.DoesNotExist:
        return None
