import uuid

import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_alter_profile_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="PendingEmailChange",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "public_id",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("email", models.EmailField(max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pending_email_change",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("email", ""), _negated=True),
                        name="users_pending_email_change_email_not_blank",
                    ),
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower(
                            django.db.models.functions.text.Trim("email")
                        ),
                        name="users_pending_email_change_email_ci_unique",
                    ),
                ],
            },
        ),
    ]
