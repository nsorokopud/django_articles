from typing import Optional

from allauth.account.models import EmailAddress
from django.contrib.auth.models import AnonymousUser
from django.db.models import BooleanField, Exists, OuterRef, Value
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404

from users.models import AuthorSubscription, User


def get_all_users() -> QuerySet[User]:
    return User.objects.all()


def get_author_with_viewer_subscription_status(
    author_id: int, viewer: User | AnonymousUser
) -> User:
    """Fetches author by ID and annotates them with a boolean field
    'is_subscribed_by_viewer', indicating whether the provided viewer is
    subscribed to the author.
    """
    annotation = (
        Exists(
            AuthorSubscription.objects.filter(subscriber=viewer, author=OuterRef("pk"))
        )
        if viewer.is_authenticated
        else Value(False, output_field=BooleanField())
    )
    queryset = User.objects.select_related("profile").annotate(
        is_subscribed_by_viewer=annotation
    )
    return get_object_or_404(
        queryset,
        pk=author_id,
    )


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
