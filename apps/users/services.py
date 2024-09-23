from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import Profile, User
from users.tokens import activation_token_generator


def create_user_profile(user: User) -> Profile:
    profile = Profile.objects.create(user=user)
    return profile


def deactivate_user(user: User) -> None:
    user.is_active = False
    user.save()


def activate_user(user):
    user.is_active = True
    user.save()


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


def get_all_supscriptions_of_user(user: User) -> list[str]:
    """Returns a list of usernames of all authors the specified user is
    subscribed to.
    """
    return [p.user.username for p in user.subscribed_profiles.all()]


def toggle_user_supscription(user: User, author: User) -> None:
    """Adds user to the list of author's subscribers if that user is not
    in the list. Otherwise removes the user from the list.
    """
    if user.pk != author.pk:
        if user not in author.profile.subscribers.all():
            author.profile.subscribers.add(user)
        else:
            author.profile.subscribers.remove(user)


def send_account_activation_email(request: HttpRequest, user: User):
    subject = "User account activation"
    encoded_user_id = urlsafe_base64_encode(force_bytes(user.pk))
    domain = get_current_site(request)
    token = activation_token_generator.make_token(user)
    protocol = "https" if request.is_secure() else "http"
    message = render_to_string("users/activation_email.html", {
        "username": user.username,
        "url": f"{protocol}://{domain}{reverse("account-activate", args=[encoded_user_id, token])}"
    })
    email = EmailMultiAlternatives(subject, message, to=[user.email])
    email.attach_alternative(message, "text/html")
    email.send()
