import os

from celery import Celery
from celery.signals import setup_logging


if "DJANGO_SETTINGS_MODULE" not in os.environ:
    raise RuntimeError("DJANGO_SETTINGS_MODULE must be set explicitly for Celery.")


app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")


@setup_logging.connect
def configure_logging(*args, **kwargs):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


app.autodiscover_tasks()
