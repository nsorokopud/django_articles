from django.urls import path

from . import views


urlpatterns = [
    path(
        "notification/<int:notification_id>/read/",
        views.ReadNotificationView.as_view(),
        name="notification-read",
    ),
    path(
        "notification/<int:notification_id>/delete/",
        views.DeleteNotificationView.as_view(),
        name="notification-delete",
    ),
]
