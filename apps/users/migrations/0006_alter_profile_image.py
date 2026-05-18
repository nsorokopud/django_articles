from django.db import migrations, models

import users.models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_remove_authorsubscription_prevent_self_subscription_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="image",
            field=models.ImageField(
                default="users/profile_images/default_avatar.jpg",
                max_length=512,
                upload_to=users.models.profile_image_upload_path,
            ),
        ),
    ]
