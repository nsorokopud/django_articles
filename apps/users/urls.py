from django.urls import path

from users import views


urlpatterns = [
    path("register/", views.UserRegistrationView.as_view(), name="registration"),
    path("post_registration/", views.PostUserRegistrationView.as_view(), name="post-registration"),
    path(
        "activate_account/<str:user_id_b64>/<str:token>/",
        views.AccountActivationView.as_view(),
        name="account-activate",
    ),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("user/profile/", views.UserProfileView.as_view(), name="user-profile"),
    path("author/<str:author_username>/", views.AuthorPageView.as_view(), name="author-page"),
    path(
        "author/<str:author_username>/subscribe/",
        views.AuthorSubscribeView.as_view(),
        name="author-subscribe",
    ),
]
