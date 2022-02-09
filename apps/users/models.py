from django.db import models
from django.contrib.auth.models import User

from PIL import Image


class Profile(models.Model):
    PICTURE_SIZE = 300

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default="users/default_avatar.jpg", upload_to="users/profile_images/")

    def __str__(self):
        return f"{self.user.username}'s profile"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        img = Image.open(self.image.path)

        if img.height > self.PICTURE_SIZE or img.width > self.PICTURE_SIZE:
            output_size = (self.PICTURE_SIZE, self.PICTURE_SIZE)
            img.thumbnail(output_size)
            img.save(self.image.path)
