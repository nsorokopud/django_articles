from django.urls import path

from users import views


urlpatterns = [
    path("register/", views.UserRegistrationView.as_view(), name="registration"),
    path(
        "post_registration/",
        views.PostUserRegistrationView.as_view(),
        name="post-registration",
    ),
    path(
        "activate_account/<str:user_id_b64>/<str:token>/",
        views.AccountActivationView.as_view(),
        name="account-activate",
    ),
    path("set_password/", views.PasswordSetView.as_view(), name="password-set"),
    path(
        "change_password/", views.PasswordChangeView.as_view(), name="password-change"
    ),
    path("change_email/", views.EmailChangeView.as_view(), name="email-change"),
    path(
        "reset_password/",
        views.PasswordResetView.as_view(),
        name="password-reset",
    ),
    path(
        "confirm_password_reset/<str:uidb64>/<str:token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "change_email_resend/",
        views.EmailChangeResendView.as_view(),
        name="email-change-resend",
    ),
    path(
        "cancel_email_change/",
        views.EmailChangeCancelView.as_view(),
        name="email-change-cancel",
    ),
    path(
        "confirm_email_change/<str:token>/",
        views.EmailChangeConfirmationView.as_view(),
        name="email-change-confirm",
    ),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("user/profile/", views.UserProfileView.as_view(), name="user-profile"),
    path(
        "author/<str:author_username>/",
        views.AuthorPageView.as_view(),
        name="author-page",
    ),
    path(
        "author/<str:author_username>/subscribe/",
        views.AuthorSubscribeView.as_view(),
        name="author-subscribe",
    ),
]
