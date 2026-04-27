from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0008_article_content_text_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="views_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
