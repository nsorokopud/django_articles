from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User
from .services.profiles import create_user_profile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created and not kwargs.get("raw", False):
        create_user_profile(user=instance)
