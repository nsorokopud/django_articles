from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_user_users_user_username_ci_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="session_auth_version",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
