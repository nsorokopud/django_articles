from django.db import models
from django.urls import reverse
from taggit.managers import TaggableManager
from tinymce.models import HTMLField

from users.models import User

from .constants import DISPLAYED_COMMENT_LENGTH


class Article(models.Model):
    title = models.CharField(max_length=256, unique=True, db_index=True)
    slug = models.SlugField(max_length=256, unique=True, db_index=True)
    category = models.ForeignKey(
        "ArticleCategory", null=True, blank=True, on_delete=models.SET_NULL
    )
    tags = TaggableManager(blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    preview_text = models.TextField(max_length=512)
    preview_image = models.ImageField(upload_to="articles/preview_images/", null=True, blank=True)
    content = HTMLField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False, db_index=True)
    users_that_liked = models.ManyToManyField(User, related_name="users_that_liked", blank=True)
    views_count = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Articles"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("article-details", kwargs={"article_slug": self.slug})


class ArticleCategory(models.Model):
    title = models.CharField(max_length=256)
    slug = models.CharField(max_length=256, unique=True, db_index=True)
    image = models.ImageField(upload_to="categories/images/", null=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["title"]

    def __str__(self):
        return self.title


class ArticleComment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    users_that_liked = models.ManyToManyField(
        User, related_name="users_that_liked_comment", blank=True
    )

    class Meta:
        verbose_name_plural = "Comments"

    def __str__(self):
        if len(self.text) > DISPLAYED_COMMENT_LENGTH:
            displayed_text = self.text[:DISPLAYED_COMMENT_LENGTH] + "..."
        else:
            displayed_text = self.text
        return f"{self.article} - {self.author} - {displayed_text}"
