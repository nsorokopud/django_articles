from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_remove_tokencounter_users_token_user_id_c1fe10_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="password_reset_token_version",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.DeleteModel(
            name="TokenCounter",
        ),
    ]
