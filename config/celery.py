import os
from logging.config import dictConfig

from celery import Celery
from celery.signals import setup_logging
from django.conf import settings


if "DJANGO_SETTINGS_MODULE" not in os.environ:
    raise RuntimeError("DJANGO_SETTINGS_MODULE must be set explicitly for Celery.")


app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")


def configure_logging(*args, **kwargs):
    dictConfig(settings.LOGGING)


if settings.LOGGING:
    setup_logging.connect(configure_logging)


app.autodiscover_tasks()
