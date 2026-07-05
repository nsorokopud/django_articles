from django.db import migrations, models


def backfill_comments_count(_apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE articles_article AS article
            SET comments_count = counts.comments_count
            FROM (
                SELECT article_id, COUNT(*) AS comments_count
                FROM articles_articlecomment
                GROUP BY article_id
            ) AS counts
            WHERE article.id = counts.article_id
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0010_article_likes_count_articlecomment_likes_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="comments_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_comments_count, migrations.RunPython.noop),
    ]
