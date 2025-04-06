from django.apps import AppConfig
from django.db.models.signals import post_save


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"

    def ready(self):
        from users.models import User

        from .signals import create_profile

        post_save.connect(create_profile, sender=User)
