import logging
from typing import Any

from celery import Task

from config.celery import app

from .services.email import EmailConfig, EmailConfigDict, mask_email, send_email
from .settings import (
    EMAIL_PERMANENT_ERRORS,
    EMAIL_TASK_BASE_RETRY_DELAY,
    EMAIL_TASK_MAX_RETRIES,
    EMAIL_TRANSIENT_ERRORS,
)


logger = logging.getLogger("default_logger")


@app.task(
    bind=True,
    max_retries=EMAIL_TASK_MAX_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_email_task(self, config_data: EmailConfigDict) -> None:
    email_config = _create_email_config(config_data)
    masked_recipients = [mask_email(r) for r in email_config.recipients]
    base_extra = {"task_id": self.request.id}

    try:
        send_email(email_config)
        logger.info(
            "Email sent successfully.",
            extra=base_extra | {"recipients": masked_recipients},
        )
    except EMAIL_PERMANENT_ERRORS:
        logger.exception(
            "Failed to send email, not retrying.",
            extra=base_extra | {"recipients": masked_recipients},
        )
        raise
    except EMAIL_TRANSIENT_ERRORS as e:
        _handle_transient_error(self, e, base_extra, masked_recipients)
    except Exception:
        logger.exception(
            "Unexpected error while sending email.",
            extra=base_extra,
        )
        raise


def _create_email_config(config_data: EmailConfigDict) -> EmailConfig:
    try:
        return EmailConfig.from_dict(config_data)
    except (TypeError, ValueError):
        logger.exception("Invalid email config provided.")
        raise


def _handle_transient_error(
    task: Task,
    error: Exception,
    base_extra: dict[str, Any],
    masked_recipients: list[str],
) -> None:
    if task.request.retries < task.max_retries:
        delay = EMAIL_TASK_BASE_RETRY_DELAY * (2**task.request.retries)
        logger.warning(
            "Failed to send email, retrying in %s seconds.",
            delay,
            extra=base_extra | {"error": str(error)},
        )
        task.retry(exc=error, countdown=delay)
    else:
        logger.exception(
            "Failed to send email after max retries.",
            extra={
                **base_extra,
                "recipients": masked_recipients,
                "max_retries": task.max_retries,
            },
        )
        raise error
