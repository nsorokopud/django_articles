from users.services import create_user_profile


def create_profile(sender, instance, created, **kwargs):
    if created:
        create_user_profile(user=instance)
