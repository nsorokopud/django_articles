from django.db import migrations, models

import articles.models
import core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0015_articlemedia"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="preview_image",
            field=models.ImageField(
                blank=True,
                upload_to=articles.models.article_preview_image_upload_path,
                validators=[core.validators.validate_uploaded_image],
            ),
        ),
    ]
