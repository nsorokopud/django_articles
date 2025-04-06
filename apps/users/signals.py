from .services import create_user_profile


def create_profile(sender, instance, created, **kwargs):
    if created and not kwargs.get("raw", False):
        create_user_profile(user=instance)
