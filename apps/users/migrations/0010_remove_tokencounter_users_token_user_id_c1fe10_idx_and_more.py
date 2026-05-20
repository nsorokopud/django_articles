from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_user_users_user_username_ci_unique"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="tokencounter",
            name="users_token_user_id_c1fe10_idx",
        ),
        migrations.AlterUniqueTogether(
            name="tokencounter",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="tokencounter",
            constraint=models.UniqueConstraint(
                fields=("user", "token_type"),
                name="users_token_counter_user_type_unique",
            ),
        ),
    ]
