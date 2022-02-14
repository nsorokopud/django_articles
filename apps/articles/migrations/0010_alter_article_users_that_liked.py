# Generated by Django 4.0.1 on 2022-02-14 15:02

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('articles', '0009_article_views_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='users_that_liked',
            field=models.ManyToManyField(blank=True, null=True, related_name='users_that_liked', to=settings.AUTH_USER_MODEL),
        ),
    ]
