from django.urls import path

from .consumers import NotificationConsumer


websocket_url_patterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi(), name="notifications")
]
