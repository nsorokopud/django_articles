from django.urls import path

from . import views


urlpatterns = [
    path("register/", views.UserRegistrationView.as_view(), name="registration"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    path("user/profile/", views.UserProfileView.as_view(), name="user-profile"),
]
