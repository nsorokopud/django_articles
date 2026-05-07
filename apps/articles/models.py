import os
import posixpath
from uuid import uuid4

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThan
from django.urls import reverse
from django.utils.text import get_valid_filename
from taggit.managers import TaggableManager
from tinymce.models import HTMLField

from users.models import User

from .settings import DISPLAYED_COMMENT_LENGTH


ARTICLE_PUBLISH_SEQUENCE_NAME = "article_publish_seq"


class ArticleStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_REVIEW = "pending_review", "Pending review"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"


class Article(models.Model):
    title = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.ForeignKey(
        "ArticleCategory", null=True, blank=True, on_delete=models.SET_NULL
    )
    tags = TaggableManager(blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    preview_text = models.TextField(max_length=512, blank=True)
    preview_image = models.ImageField(upload_to="articles/preview_images/", blank=True)
    content = HTMLField(blank=True)
    content_text = models.TextField(blank=True, editable=False)
    search_vector = models.GeneratedField(
        expression=(
            SearchVector("title", weight="A", config="english")
            + SearchVector("preview_text", weight="B", config="english")
            + SearchVector("content_text", weight="C", config="english")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
        null=True,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=ArticleStatus.choices,
        default=ArticleStatus.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    publish_sequence = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        editable=False,
    )
    modified_at = models.DateTimeField(auto_now=True)
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_articles",
    )
    users_that_liked = models.ManyToManyField(
        User, related_name="liked_articles", blank=True
    )
    views_count = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0, db_index=True)
    comments_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Articles"

        permissions = [("can_review_article", "Can review articles")]

        indexes = [
            models.Index(
                fields=["author", "-publish_sequence", "-id"],
                name="art_author_pub_seq_id_desc_idx",
                condition=Q(status=ArticleStatus.PUBLISHED),
            ),
            models.Index(
                fields=["-publish_sequence"],
                name="article_publish_seq_desc_idx",
                condition=Q(status=ArticleStatus.PUBLISHED),
            ),
            GinIndex(
                fields=["title"],
                name="article_title_trigram_idx",
                opclasses=["gin_trgm_ops"],
                condition=Q(status=ArticleStatus.PUBLISHED),
            ),
            GinIndex(
                fields=["search_vector"],
                name="article_search_vector_gin_idx",
                condition=Q(status=ArticleStatus.PUBLISHED),
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["publish_sequence"],
                condition=Q(publish_sequence__isnull=False),
                name="uniq_article_publish_sequence_not_null",
            ),
            models.CheckConstraint(
                condition=(
                    Q(published_at__isnull=True, publish_sequence__isnull=True)
                    | Q(published_at__isnull=False, publish_sequence__isnull=False)
                ),
                name="article_publish_fields_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=ArticleStatus.PUBLISHED,
                        published_at__isnull=False,
                        publish_sequence__isnull=False,
                    )
                    | Q(
                        status__in=[
                            ArticleStatus.DRAFT,
                            ArticleStatus.PENDING_REVIEW,
                            ArticleStatus.REJECTED,
                        ],
                        published_at__isnull=True,
                        publish_sequence__isnull=True,
                    )
                ),
                name="art_status_matches_publ_fields",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=ArticleStatus.DRAFT)
                    | (
                        GreaterThan(Length(Trim("title")), Value(0))
                        & GreaterThan(Length(Trim("preview_text")), Value(0))
                        & GreaterThan(Length(Trim("content_text")), Value(0))
                    )
                ),
                name="art_non_draft_core_fields_have_text",
            ),
        ]

    def __str__(self):
        return self.title or f"Article #{self.pk}"

    def get_absolute_url(self):
        return reverse("article-details", kwargs={"article_slug": self.slug})

    @property
    def is_published(self) -> bool:
        return self.status == ArticleStatus.PUBLISHED

    @property
    def views(self) -> int:
        """Returns current total (DB + cache) view count."""
        from .cache.view_counts import get_cached_article_views

        views_delta = get_cached_article_views(self.id)
        return self.views_count + views_delta


class ArticleCategory(models.Model):
    title = models.CharField(max_length=256)
    slug = models.SlugField(max_length=256, unique=True)
    image = models.ImageField(upload_to="categories/images/", blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["title"]

    def __str__(self):
        return self.title


def article_inline_media_upload_path(instance, filename) -> str:
    raw_base_name = os.path.basename(filename)
    base_name, extension = os.path.splitext(raw_base_name)

    safe_base_name = get_valid_filename(base_name).strip("._-") or "file"
    safe_extension = (
        get_valid_filename(extension.lower()).strip("._") if extension else ""
    )

    filename = f"{safe_base_name}_{uuid4().hex}"
    if safe_extension:
        filename = f"{filename}.{safe_extension}"

    return posixpath.join(
        "articles",
        "uploads",
        str(instance.article.author_id),
        str(instance.article_id),
        filename,
    )


class ArticleMedia(models.Model):
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="media_files"
    )
    file = models.FileField(upload_to=article_inline_media_upload_path, max_length=512)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    unreferenced_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["unreferenced_at", "id"], name="art_media_cleanup_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"Media for {self.article} - {self.file.name}"


class ArticleComment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    users_that_liked = models.ManyToManyField(
        User, related_name="liked_comments", blank=True
    )
    likes_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Comments"

    def __str__(self):
        if len(self.text) > DISPLAYED_COMMENT_LENGTH:
            displayed_text = self.text[:DISPLAYED_COMMENT_LENGTH] + "..."
        else:
            displayed_text = self.text
        return f"{self.article} - {self.author} - {displayed_text}"
