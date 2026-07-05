from django.urls import path

from users.views.auth import (
    PasswordChangeView,
    PasswordResetView,
    PasswordSetView,
    UserLoginView,
    UserPasswordResetConfirmView,
)
from users.views.email import (
    EmailChangeCancelView,
    EmailChangeConfirmationView,
    EmailChangeResendView,
    EmailChangeView,
)
from users.views.registration import (
    AccountActivationView,
    PostUserRegistrationView,
    UserRegistrationView,
)
from users.views.user_pages import (
    AuthorPageView,
    AuthorSubscribeView,
    AuthorUnsubscribeView,
    UserProfileView,
)


urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="registration"),
    path(
        "post_registration/",
        PostUserRegistrationView.as_view(),
        name="post-registration",
    ),
    path(
        "activate_account/<str:user_id_b64>/<str:token>/",
        AccountActivationView.as_view(),
        name="account-activate",
    ),
    path("set_password/", PasswordSetView.as_view(), name="password-set"),
    path("change_password/", PasswordChangeView.as_view(), name="password-change"),
    path("change_email/", EmailChangeView.as_view(), name="email-change"),
    path("reset_password/", PasswordResetView.as_view(), name="password-reset"),
    path(
        "confirm_password_reset/<str:uidb64>/<str:token>/",
        UserPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "change_email_resend/",
        EmailChangeResendView.as_view(),
        name="email-change-resend",
    ),
    path(
        "cancel_email_change/",
        EmailChangeCancelView.as_view(),
        name="email-change-cancel",
    ),
    path(
        "confirm_email_change/<uuid:pending_email_change_public_id>/<str:token>/",
        EmailChangeConfirmationView.as_view(),
        name="email-change-confirm",
    ),
    path("login/", UserLoginView.as_view(), name="login"),
    path("user/profile/", UserProfileView.as_view(), name="user-profile"),
    path("author/<int:author_id>/", AuthorPageView.as_view(), name="author-page"),
    path(
        "author/<int:author_id>/subscribe/",
        AuthorSubscribeView.as_view(),
        name="author-subscribe",
    ),
    path(
        "author/<int:author_id>/unsubscribe/",
        AuthorUnsubscribeView.as_view(),
        name="author-unsubscribe",
    ),
]
