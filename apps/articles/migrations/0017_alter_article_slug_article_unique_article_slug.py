from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0016_alter_article_preview_image"),
        (
            "taggit",
            "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="slug",
            field=models.SlugField(max_length=200),
        ),
        migrations.AddConstraint(
            model_name="article",
            constraint=models.UniqueConstraint(
                fields=("slug",), name="unique_article_slug"
            ),
        ),
    ]
