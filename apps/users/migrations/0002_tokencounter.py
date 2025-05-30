# Generated by Django 5.1.1 on 2025-04-29 12:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TokenCounter",
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
                    "token_type",
                    models.CharField(
                        choices=[
                            ("account activation", "Account Activation"),
                            ("email change", "Email Change"),
                            ("password change", "Password Change"),
                        ],
                        max_length=32,
                    ),
                ),
                ("token_count", models.IntegerField(default=0)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["user", "token_type"],
                        name="users_token_user_id_c1fe10_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "token_type__in",
                                [
                                    "account activation",
                                    "email change",
                                    "password change",
                                ],
                            )
                        ),
                        name="users_tokencounter_token_type_valid",
                    )
                ],
                "unique_together": {("user", "token_type")},
            },
        ),
    ]
