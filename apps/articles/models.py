from django.db import models
from django.urls import reverse
from taggit.managers import TaggableManager
from tinymce.models import HTMLField

from users.models import User

from .settings import DISPLAYED_COMMENT_LENGTH


ARTICLE_PUBLISH_SEQUENCE_NAME = "article_publish_seq"


class Article(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.ForeignKey(
        "ArticleCategory", null=True, blank=True, on_delete=models.SET_NULL
    )
    tags = TaggableManager(blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    preview_text = models.TextField(max_length=512)
    preview_image = models.ImageField(upload_to="articles/preview_images/", blank=True)
    content = HTMLField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    publish_sequence = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        editable=False,
    )
    modified_at = models.DateTimeField(auto_now=True)
    users_that_liked = models.ManyToManyField(
        User, related_name="liked_articles", blank=True
    )
    views_count = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Articles"

        indexes = [
            models.Index(
                fields=["author", "-publish_sequence", "-id"],
                name="art_author_pub_seq_id_desc_idx",
                condition=models.Q(publish_sequence__isnull=False),
            ),
            models.Index(
                fields=["-publish_sequence"],
                name="article_publish_seq_desc_idx",
                condition=models.Q(publish_sequence__isnull=False),
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["publish_sequence"],
                condition=models.Q(publish_sequence__isnull=False),
                name="uniq_article_publish_sequence_not_null",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(published_at__isnull=True, publish_sequence__isnull=True)
                    | models.Q(
                        published_at__isnull=False, publish_sequence__isnull=False
                    )
                ),
                name="article_publish_fields_consistent",
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_title = self.title

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("article-details", kwargs={"article_slug": self.slug})

    def save(self, *args, **kwargs):
        from .services import generate_unique_article_slug

        is_new = self.pk is None
        title_changed = self.title != self._original_title
        is_unpublished = self.published_at is None and self.publish_sequence is None

        if not self.slug:
            self.slug = generate_unique_article_slug(self.title)
        elif not is_new and is_unpublished and title_changed:
            self.slug = generate_unique_article_slug(self.title)

        super().save(*args, **kwargs)
        self._original_title = self.title

    @property
    def views(self) -> int:
        """Returns current total (DB + cache) view count."""
        from .cache import get_cached_article_views

        views_delta = get_cached_article_views(self.id)
        return self.views_count + views_delta


class ArticleCategory(models.Model):
    title = models.CharField(max_length=256)
    slug = models.CharField(max_length=256, unique=True, db_index=True)
    image = models.ImageField(upload_to="categories/images/", blank=True)

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
        User, related_name="liked_comments", blank=True
    )

    class Meta:
        verbose_name_plural = "Comments"

    def __str__(self):
        if len(self.text) > DISPLAYED_COMMENT_LENGTH:
            displayed_text = self.text[:DISPLAYED_COMMENT_LENGTH] + "..."
        else:
            displayed_text = self.text
        return f"{self.article} - {self.author} - {displayed_text}"
