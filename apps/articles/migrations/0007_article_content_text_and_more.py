import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0006_alter_article_content_alter_article_preview_text_and_more"),
        (
            "taggit",
            "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="content_text",
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name="article",
            name="search_vector",
            field=models.GeneratedField(
                db_persist=True,
                expression=(
                    django.contrib.postgres.search.SearchVector(
                        "title", weight="A", config="english"
                    )
                    + django.contrib.postgres.search.SearchVector(
                        "preview_text", weight="B", config="english"
                    )
                    + django.contrib.postgres.search.SearchVector(
                        "content_text", weight="C", config="english"
                    )
                ),
                output_field=django.contrib.postgres.search.SearchVectorField(),
                null=True,
                editable=False,
            ),
        ),
        migrations.AddIndex(
            model_name="article",
            index=django.contrib.postgres.indexes.GinIndex(
                condition=models.Q(("status", "published")),
                fields=["search_vector"],
                name="article_search_vector_gin_idx",
            ),
        ),
    ]
