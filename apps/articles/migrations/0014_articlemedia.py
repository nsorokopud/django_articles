import django.db.models.deletion
from django.db import migrations, models

import articles.models


class Migration(migrations.Migration):

    dependencies = [
        (
            "articles",
            "0013_remove_article_art_non_draft_core_fields_not_blank_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="ArticleMedia",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        max_length=512,
                        upload_to=articles.models.article_inline_media_upload_path,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "unreferenced_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "article",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="media_files",
                        to="articles.article",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["unreferenced_at", "id"], name="art_media_cleanup_idx"
                    )
                ],
            },
        ),
    ]
