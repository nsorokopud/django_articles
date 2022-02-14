from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User

from ckeditor_uploader.fields import RichTextUploadingField
from taggit.managers import TaggableManager


class Article(models.Model):
    title = models.CharField(max_length=256, unique=True)
    slug = models.SlugField(max_length=256, unique=True)
    category = models.ForeignKey(
        "ArticleCategory", null=True, blank=True, on_delete=models.SET_NULL
    )
    tags = TaggableManager(blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    preview_text = models.CharField(max_length=512)
    preview_image = models.ImageField(upload_to="articles/preview_images/", null=True, blank=True)
    content = RichTextUploadingField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    users_that_liked = models.ManyToManyField(
        User, related_name="users_that_liked", null=True, blank=True
    )
    views_count = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Articles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.author} - [{self.created_at}]"

    def get_absolute_url(self):
        return reverse("article-details", kwargs={"article_slug": self.slug})

    def get_likes_count(self):
        return self.users_that_liked.count()

    def get_comments_count(self):
        return ArticleComment.objects.filter(article=self).count()


class ArticleCategory(models.Model):
    title = models.CharField(max_length=256)
    slug = models.CharField(max_length=256, unique=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def get_articles_count(self):
        return Article.objects.filter(is_published=True, category=self).count()


class ArticleComment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    users_that_liked = models.ManyToManyField(User, related_name="users_that_liked_comment")

    class Meta:
        verbose_name_plural = "Comments"

    def __str__(self):
        displayed_comment_length = 25
        if len(self.text) > displayed_comment_length:
            displayed_text = self.text[:displayed_comment_length] + "..."
        else:
            displayed_text = self.text
        return f"{self.article} - {self.author} - {displayed_text}"

    def get_likes_count(self):
        return self.users_that_liked.count()
