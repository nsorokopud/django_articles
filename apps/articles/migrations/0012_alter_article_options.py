from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0011_article_comments_count"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="article",
            options={
                "permissions": [("can_review_article", "Can review articles")],
                "verbose_name_plural": "Articles",
            },
        ),
    ]
