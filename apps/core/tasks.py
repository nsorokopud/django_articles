import logging

from celery import Task

from config.celery import app

from .services.email import EmailConfig, EmailConfigDict, mask_email, send_email
from .settings import (
    EMAIL_PERMANENT_ERRORS,
    EMAIL_TASK_BASE_RETRY_DELAY,
    EMAIL_TASK_EXPONENTIAL_BACKOFF_FACTOR,
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

    try:
        send_email(email_config)
        logger.info(
            "Email sent successfully. Recipients: %s",
            masked_recipients,
        )
    except EMAIL_PERMANENT_ERRORS:
        logger.exception(
            "Failed to send email, not retrying. Task ID: %s; recipients: %s",
            self.request.id,
            masked_recipients,
        )
        raise
    except EMAIL_TRANSIENT_ERRORS as e:
        _handle_transient_error(self, e, masked_recipients)
    except Exception:
        logger.exception(
            "Unexpected error while sending email. Task ID: %s", self.request.id
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
    masked_recipients: list[str],
) -> None:
    if task.request.retries < task.max_retries:
        delay = EMAIL_TASK_BASE_RETRY_DELAY * (
            EMAIL_TASK_EXPONENTIAL_BACKOFF_FACTOR**task.request.retries
        )
        logger.warning(
            "Failed to send email, retrying in %s seconds. Task ID: %s; error: %s",
            delay,
            task.request.id,
            error,
        )
        task.retry(exc=error, countdown=delay)
    else:
        logger.exception(
            (
                "Failed to send email after max retries (%s). "
                "Task ID: %s; recipients: %s"
            ),
            EMAIL_TASK_MAX_RETRIES,
            task.request.id,
            masked_recipients,
        )
        raise error
