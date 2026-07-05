from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_remove_profile_subscribers_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="authorsubscription",
            name="prevent_self_subscription",
        ),
        migrations.RemoveConstraint(
            model_name="authorsubscription",
            name="unique_subscription",
        ),
        migrations.RemoveIndex(
            model_name="authorsubscription",
            name="users_autho_subscri_3ddef0_idx",
        ),
        migrations.RemoveIndex(
            model_name="authorsubscription",
            name="users_autho_author__7de617_idx",
        ),
        migrations.AddField(
            model_name="user",
            name="unread_notifications_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="profile",
            name="notification_emails_allowed",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddConstraint(
            model_name="authorsubscription",
            constraint=models.CheckConstraint(
                condition=models.Q(("subscriber", models.F("author")), _negated=True),
                name="sub_prevent_self_subscription",
            ),
        ),
        migrations.AddConstraint(
            model_name="authorsubscription",
            constraint=models.UniqueConstraint(
                fields=("subscriber", "author"), name="sub_subscriber_author_unique"
            ),
        ),
    ]
