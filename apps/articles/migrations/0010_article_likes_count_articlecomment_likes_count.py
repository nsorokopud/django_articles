from django.db import migrations, models


def backfill_likes_count(_apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        # Articles
        cursor.execute(
            """
            UPDATE articles_article AS article
            SET likes_count = counts.likes_count
            FROM (
                SELECT article_id, COUNT(*) AS likes_count
                FROM articles_article_users_that_liked
                GROUP BY article_id
            ) AS counts
            WHERE article.id = counts.article_id
            """
        )

        # Comments
        cursor.execute(
            """
            UPDATE articles_articlecomment AS comment
            SET likes_count = counts.likes_count
            FROM (
                SELECT articlecomment_id, COUNT(*) AS likes_count
                FROM articles_articlecomment_users_that_liked
                GROUP BY articlecomment_id
            ) AS counts
            WHERE comment.id = counts.articlecomment_id
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0009_article_article_title_trigram_idx"),
    ]

    operations = [
        # Add counters without an index first so the backfill does not also maintain
        # the likes_count index while updating existing rows.
        migrations.AddField(
            model_name="article",
            name="likes_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="articlecomment",
            name="likes_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_likes_count, migrations.RunPython.noop),
        # Add the index after backfill because articles can be ordered by likes_count.
        migrations.AlterField(
            model_name="article",
            name="likes_count",
            field=models.PositiveIntegerField(default=0, db_index=True),
        ),
    ]
