from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_add_last_event_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                condition=models.Q(("read_at__isnull", False)),
                fields=["read_at", "id"],
                name="notif_read_cleanup_idx",
            ),
        ),
    ]
