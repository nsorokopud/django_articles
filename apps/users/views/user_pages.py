import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from users.forms import ProfileUpdateForm, UserUpdateForm

from ..cache import get_cached_subscribers_count
from ..models import User
from ..selectors import (
    get_all_subscriptions_of_user,
    get_author_with_viewer_subscription_status,
)
from ..services import toggle_user_subscription


logger = logging.getLogger("default_logger")


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
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect(request.path)

        context = self.get_context_data(user_form=user_form, profile_form=profile_form)
        return render(request, self.template_name, context)

    def get_context_data(self, user_form=None, profile_form=None) -> dict[str, Any]:
        return {
            "user_form": user_form or UserUpdateForm(instance=self.request.user),
            "profile_form": profile_form
            or ProfileUpdateForm(instance=self.request.user.profile),
            "subscribed_authors": get_all_subscriptions_of_user(self.request.user),
        }


class AuthorPageView(TemplateView):
    template_name = "users/author_page.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        author = get_author_with_viewer_subscription_status(
            self.kwargs.get("author_id"), self.request.user
        )
        subscribers_count = get_cached_subscribers_count(author)

        user = self.request.user
        context["author"] = author
        context["author_image_url"] = author.profile.image.url
        context["subscribers_count"] = subscribers_count
        context["is_viewer_subscribed"] = (
            author.is_subscribed_by_viewer if user.is_authenticated else False
        )
        return context


class AuthorSubscribeView(LoginRequiredMixin, View):
    def post(self, request, author_id: int) -> HttpResponseRedirect:
        author = get_object_or_404(User, pk=author_id)

        if request.user == author:
            messages.error(
                request, "You cannot subscribe to or unsubscribe from yourself."
            )
            return redirect("author-page", author_id=author.id)

        try:
            subscribed = toggle_user_subscription(request.user, author)
            message = (
                f"You are now subscribed to {author.username}."
                if subscribed
                else f"You unsubscribed from {author.username}."
            )
            messages.success(request, message)
        except ValidationError:
            logger.exception(
                "Error while toggling subscription of user %s to author %s",
                request.user.username,
                author.username,
            )
            messages.error(
                request, "Something went wrong while managing your subscription."
            )
        return redirect("author-page", author_id=author_id)
