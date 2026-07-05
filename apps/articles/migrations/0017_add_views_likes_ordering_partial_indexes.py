from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0016_alter_article_slug_article_unique_article_slug"),
        (
            "taggit",
            "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="article",
            index=models.Index(
                condition=models.Q(("status", "published")),
                fields=["-views_count", "-published_at", "-id"],
                name="art_pub_views_pub_at_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(
                condition=models.Q(("status", "published")),
                fields=["-likes_count", "-published_at", "-id"],
                name="art_pub_likes_pub_at_id_idx",
            ),
        ),
    ]
