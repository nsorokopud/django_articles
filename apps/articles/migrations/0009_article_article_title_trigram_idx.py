import django.contrib.postgres.indexes
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0008_alter_article_views_count"),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name="article",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["title"],
                name="article_title_trigram_idx",
                opclasses=["gin_trgm_ops"],
                condition=models.Q(status="published"),
            ),
        ),
    ]
