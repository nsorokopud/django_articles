from django.urls import path

from . import views


urlpatterns = [
    path(
        "notification/<int:notification_id>/read/",
        views.ReadNotificationView.as_view(),
        name="notification-read",
    )
]
