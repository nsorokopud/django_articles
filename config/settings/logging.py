import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


LOGGING_ENABLED = bool(int(os.getenv("ENABLE_LOGGING", "0")))
LOG_TO_CONSOLE = bool(int(os.getenv("LOG_TO_CONSOLE", "0")))
LOGS_PATH = os.path.join(BASE_DIR, os.getenv("LOGS_PATH", "logs"))

if LOGGING_ENABLED:
    os.makedirs(LOGS_PATH, exist_ok=True)

    logging_handlers = {
        "file_general": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "general.log"),
            "maxBytes": 1024 * 1024 * 50,  # 50 MB
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_uncaught_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "uncaught_errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "exception",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_worker_general": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_worker.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_worker_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_worker_errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "exception",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_beat_general": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_beat.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_beat_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_beat_errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "exception",
            "filters": ["host_name"],
            "delay": True,
        },
    }

    if LOG_TO_CONSOLE:
        logging_handlers["console"] = {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
        }

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "host_name": {"()": "core.logging_filters.HostNameFilter"},
        },
        "formatters": {
            "default": {
                "format": (
                    "{asctime} - [{levelname}] - {host_name}:{processName}:{process}\n"
                    "{name}:{funcName}:{lineno} - {message}"
                ),
                "style": "{",
            },
            "exception": {
                "format": "{asctime} - [{levelname}] - {host_name}:{processName}:"
                "{process}\n{message}",
                "style": "{",
            },
        },
        "handlers": logging_handlers,
        "root": {
            "handlers": [
                h
                for h in ["console", "file_general", "file_errors"]
                if h in logging_handlers
            ],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
        },
        "loggers": {
            "django": {
                "handlers": [h for h in ["console"] if h in logging_handlers],
                "level": "INFO",
                "propagate": False,
            },
            "django.server": {
                "handlers": [h for h in ["console"] if h in logging_handlers],
                "level": "INFO",
                "propagate": False,
            },
            "django.request": {
                "handlers": [
                    h
                    for h in ["console", "file_uncaught_errors"]
                    if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
            "daphne": {
                "handlers": [
                    h for h in ["console", "file_errors"] if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
            "celery": {
                "handlers": [
                    h
                    for h in [
                        "file_celery_worker_general",
                        "file_celery_worker_errors",
                    ]
                    if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
            "celery.beat": {
                "handlers": [
                    h
                    for h in ["file_celery_beat_general", "file_celery_beat_errors"]
                    if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
            "py.warnings": {
                "handlers": ["file_general"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }
else:
    LOGGING = {}
