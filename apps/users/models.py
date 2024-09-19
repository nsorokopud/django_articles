from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(
        default="users/profile_images/default_avatar.jpg", upload_to="users/profile_images/"
    )
    subscribers = models.ManyToManyField(User, related_name="subscribed_profiles")

    def __str__(self):
        return f"{self.user.username}'s profile"
