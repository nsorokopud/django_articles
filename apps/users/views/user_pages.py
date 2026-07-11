import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from users.forms import ProfileUpdateForm, UserUpdateForm

from ..models import User
from ..selectors import (
    find_authors_subscribed_by_user,
    get_author_with_viewer_subscription_status,
)
from ..services.profiles import update_user_profile
from ..services.subscriptions import set_author_subscription


logger = logging.getLogger(__name__)


class UserProfileView(LoginRequiredMixin, View):
    login_url = reverse_lazy("login")
    template_name = "users/profile.html"

    def get(self, request) -> HttpResponse:
        context = self.get_context_data()
        return render(request, self.template_name, context)

    def post(self, request) -> HttpResponse | HttpResponseRedirect:
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=request.user.profile
        )

        if user_form.is_valid() and profile_form.is_valid():
            update_user_profile(
                user=request.user,
                username=user_form.cleaned_data["username"],
                image=profile_form.cleaned_data.get("image"),
                image_changed="image" in profile_form.changed_data,
                notification_emails_allowed=profile_form.cleaned_data[
                    "notification_emails_allowed"
                ],
            )

            messages.success(request, "Profile updated successfully.")
            return redirect(request.path)

        context = self.get_context_data(user_form=user_form, profile_form=profile_form)
        return render(request, self.template_name, context)

    def get_context_data(self, user_form=None, profile_form=None) -> dict[str, Any]:
        return {
            "user_form": user_form or UserUpdateForm(instance=self.request.user),
            "profile_form": profile_form
            or ProfileUpdateForm(instance=self.request.user.profile),
            "subscribed_authors": find_authors_subscribed_by_user(self.request.user),
        }


class AuthorPageView(TemplateView):
    template_name = "users/author_page.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        author = get_author_with_viewer_subscription_status(
            self.kwargs.get("author_id"), self.request.user
        )

        user = self.request.user
        context["author"] = author
        context["author_image_url"] = author.profile.image.url
        context["subscribers_count"] = author.subscribers.count()
        context["is_viewer_subscribed"] = (
            author.is_subscribed_by_viewer if user.is_authenticated else False
        )
        return context


@method_decorator(
    ratelimit(key="core.ratelimit.user_or_ip", rate="30/m", method="POST", block=True),
    name="dispatch",
)
class AuthorSubscriptionBaseView(LoginRequiredMixin, View):
    should_subscribe: bool
    success_changed_message: str
    success_unchanged_message: str

    def post(self, request, author_id: int) -> HttpResponseRedirect:
        author = get_object_or_404(User, pk=author_id, is_active=True)

        try:
            _, changed = set_author_subscription(
                subscriber=request.user,
                author=author,
                should_subscribe=self.should_subscribe,
            )
        except ValidationError as e:
            messages.error(request, e.messages[0] if e.messages else str(e))
            return redirect("author-page", author_id=author.id)

        if changed:
            messages.success(
                request, self.success_changed_message.format(author=author)
            )
        else:
            messages.info(request, self.success_unchanged_message.format(author=author))

        return redirect("author-page", author_id=author.id)


class AuthorSubscribeView(AuthorSubscriptionBaseView):
    should_subscribe = True
    success_changed_message = "You are now subscribed to {author.username}."
    success_unchanged_message = "You are already subscribed to {author.username}."


class AuthorUnsubscribeView(AuthorSubscriptionBaseView):
    should_subscribe = False
    success_changed_message = "You unsubscribed from {author.username}."
    success_unchanged_message = "You were not subscribed to {author.username}."
