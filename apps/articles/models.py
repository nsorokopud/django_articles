from django.db import models


class ArticleCategory(models.Model):
    title = models.CharField(max_length=256)
    slug = models.CharField(max_length=256, unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.title
