from typing import Optional

from django.contrib.auth.models import AnonymousUser
from django.db.models import BooleanField, Exists, OuterRef, Value
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404

from users.models import AuthorSubscription, PendingEmailChange, User


def get_author_with_viewer_subscription_status(
    author_id: int, viewer: User | AnonymousUser
) -> User:
    """Fetches an active author by ID and annotates them with a boolean field
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

    queryset = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .annotate(is_subscribed_by_viewer=annotation)
    )

    return get_object_or_404(queryset, pk=author_id)


def get_user_by_id(user_id: int) -> User:
    return User.objects.get(id=user_id)


def find_authors_subscribed_by_user(user: User) -> QuerySet[User]:
    return user.subscribed_to_authors.only("id", "username")


def get_pending_email_change(user: User) -> Optional[PendingEmailChange]:
    try:
        return user.pending_email_change
    except PendingEmailChange.DoesNotExist:
        return None
