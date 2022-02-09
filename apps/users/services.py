import os

from django.conf import settings


def delete_profile_image(image_name: str) -> None:
    os.remove(os.path.join(settings.MEDIA_ROOT, "users", "profile_images", image_name))
