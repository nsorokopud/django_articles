from django.urls import path

from . import views


urlpatterns = [
    path(
        "notification/<int:notification_id>/read/",
        views.NotificationReadView.as_view(),
        name="notification-read",
    ),
    path(
        "notification/<int:notification_id>/delete/",
        views.NotificationDeleteView.as_view(),
        name="notification-delete",
    ),
    path(
        "notifications/list/",
        views.notifications_list,
        name="notifications-list",
    ),
    path(
        "notifications/unread_count/",
        views.notifications_unread_count,
        name="notifications-unread-count",
    ),
]
