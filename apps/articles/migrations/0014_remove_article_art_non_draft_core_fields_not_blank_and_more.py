import django.db.models.functions.text
import django.db.models.lookups
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0013_alter_article_options"),
        (
            "taggit",
            "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="article",
            name="art_non_draft_core_fields_not_blank",
        ),
        migrations.AddConstraint(
            model_name="article",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("status", "draft"),
                    models.Q(
                        django.db.models.lookups.GreaterThan(
                            django.db.models.functions.text.Length(
                                django.db.models.functions.text.Trim("title")
                            ),
                            models.Value(0),
                        ),
                        django.db.models.lookups.GreaterThan(
                            django.db.models.functions.text.Length(
                                django.db.models.functions.text.Trim("preview_text")
                            ),
                            models.Value(0),
                        ),
                        django.db.models.lookups.GreaterThan(
                            django.db.models.functions.text.Length(
                                django.db.models.functions.text.Trim("content_text")
                            ),
                            models.Value(0),
                        ),
                    ),
                    _connector="OR",
                ),
                name="art_non_draft_core_fields_have_text",
            ),
        ),
    ]
