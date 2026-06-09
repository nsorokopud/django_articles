import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "notifications",
            "0004_remove_notification_notif_read_read_at_id_idx_and_more",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="notification",
            options={"ordering": ("-last_event_at", "-id")},
        ),
        migrations.RemoveIndex(
            model_name="notification",
            name="notif_recipient_id_desc_idx",
        ),
        migrations.RemoveIndex(
            model_name="notification",
            name="notif_unread_recip_id_desc_idx",
        ),
        migrations.AddField(
            model_name="notification",
            name="last_event_at",
            field=models.DateTimeField(
                db_index=True, default=django.utils.timezone.now
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "-last_event_at", "-id"],
                name="notif_rec_event_id_desc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                condition=models.Q(("read_at__isnull", True)),
                fields=["recipient", "-last_event_at", "-id"],
                name="notif_unread_rec_event_id_idx",
            ),
        ),
    ]
