from dataclasses import asdict
from unittest.mock import MagicMock, patch

from celery.exceptions import Retry
from django.test import TestCase, override_settings

from core.services.email import EmailConfig, mask_email
from core.settings import (
    EMAIL_PERMANENT_ERRORS,
    EMAIL_TASK_BASE_RETRY_DELAY,
    EMAIL_TASK_MAX_RETRIES,
)
from core.tasks import EMAIL_TRANSIENT_ERRORS, send_email_task


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestSendEmailTask(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.valid_config = {
            "recipients": ["test@test.com"],
            "subject": "Test",
            "text_content": "Test",
        }

    @patch("core.tasks.logger")
    @patch("core.tasks.send_email")
    def test_success(self, mock_send_email, mock_logger):
        mock_logger.info = MagicMock()
        send_email_task.delay(self.valid_config)

        mock_send_email.assert_called_once()
        self.assertEqual(
            asdict(mock_send_email.call_args[0][0]),
            asdict(EmailConfig.from_dict(self.valid_config)),
        )

        mock_logger.info.assert_called_once()
        log_args, _ = mock_logger.info.call_args

        masked_recipients = [mask_email(r) for r in self.valid_config["recipients"]]
        self.assertEqual(log_args[0], "Email sent successfully. Recipients: %s")
        self.assertEqual(log_args[1], masked_recipients)

    @patch("core.tasks.send_email")
    def test_invalid_config(self, mock_send_email):
        invalid_config = {
            "recipients": "not-a-list",
            "subject": "Test",
            "text_content": "Test",
        }

        with self.assertLogs("core.tasks", level="ERROR") as logs:
            with self.assertRaises(ValueError):
                send_email_task.delay(invalid_config)

        self.assertEqual(len(logs.output), 1)
        self.assertIn("Invalid email config provided.", logs.output[0])
        mock_send_email.assert_not_called()

    @patch("celery.app.task.Task.request")
    @patch("core.tasks.send_email")
    def test_permanent_error(self, mock_send_email, mock_request):
        mock_send_email.side_effect = EMAIL_PERMANENT_ERRORS[0](1, "Permanent error")
        mock_request.id = 12345
        mock_request.retries = 0
        mock_request.called_directly = False

        with (
            patch("core.tasks.send_email_task.retry") as mock_retry,
            self.assertRaises(EMAIL_PERMANENT_ERRORS[0]),
            patch("core.tasks.logger") as mock_logger,
        ):
            mock_logger.exception = MagicMock()
            send_email_task.delay(self.valid_config)

        mock_retry.assert_not_called()
        mock_logger.exception.assert_called_once()
        log_args, _ = mock_logger.exception.call_args

        self.assertEqual(
            log_args[0],
            "Failed to send email, not retrying. Task ID: %s; recipients: %s",
        )
        self.assertEqual(log_args[1], mock_request.id)
        masked_recipients = [mask_email(r) for r in self.valid_config["recipients"]]
        self.assertEqual(log_args[2], masked_recipients)

    @patch("celery.app.task.Task.request")
    @patch("core.tasks.send_email")
    def test_transient_error_before_max_retries(self, mock_send_email, mock_request):
        mock_send_email.side_effect = EMAIL_TRANSIENT_ERRORS[0]("Transient error")
        mock_request.id = 12345
        mock_request.retries = 0
        mock_request.called_directly = False

        with (
            patch("core.tasks.send_email_task.retry") as mock_retry,
            patch("core.tasks.logger") as mock_logger,
        ):
            mock_logger.warning = MagicMock()
            send_email_task.delay(self.valid_config)

        mock_retry.assert_called_once_with(
            exc=mock_send_email.side_effect, countdown=EMAIL_TASK_BASE_RETRY_DELAY
        )

        mock_logger.warning.assert_called_once()
        log_args, _ = mock_logger.warning.call_args

        self.assertEqual(
            log_args[0],
            "Failed to send email, retrying in %s seconds. Task ID: %s; error: %s",
        )
        self.assertEqual(log_args[1], EMAIL_TASK_BASE_RETRY_DELAY)
        self.assertEqual(log_args[2], mock_request.id)
        self.assertEqual(log_args[3], mock_send_email.side_effect)

    @patch("celery.app.task.Task.request")
    @patch("core.tasks.send_email")
    def test_transient_error_after_max_retries(self, mock_send_email, mock_request):
        mock_request.id = 12345
        mock_send_email.side_effect = EMAIL_TRANSIENT_ERRORS[0]("Transient error")
        mock_request.retries = EMAIL_TASK_MAX_RETRIES
        mock_request.called_directly = False

        with (
            patch("core.tasks.send_email_task.retry") as mock_retry,
            self.assertRaises(EMAIL_TRANSIENT_ERRORS[0]),
            patch("core.tasks.logger") as mock_logger,
        ):
            mock_logger.exception = MagicMock()
            send_email_task.delay(self.valid_config)

        mock_retry.assert_not_called()
        mock_logger.exception.assert_called_once()
        log_args, _ = mock_logger.exception.call_args

        self.assertEqual(
            log_args[0],
            (
                "Failed to send email after max retries (%s). "
                "Task ID: %s; recipients: %s"
            ),
        )
        self.assertEqual(log_args[1], EMAIL_TASK_MAX_RETRIES)
        self.assertEqual(log_args[2], mock_request.id)
        self.assertEqual(
            log_args[3], [mask_email(r) for r in self.valid_config["recipients"]]
        )

    @patch("core.tasks.logger")
    @patch("celery.app.task.Task.request")
    @patch("core.tasks.send_email")
    def test_exponential_retry_backoff(
        self, mock_send_email, mock_request, mock_logger
    ):
        mock_request.id = 12345
        mock_request.retries = 0
        mock_request.called_directly = False
        mock_send_email.side_effect = EMAIL_TRANSIENT_ERRORS[0]("Transient error")
        mock_logger.warning = MagicMock()

        for _ in range(EMAIL_TASK_MAX_RETRIES):
            with self.assertRaises(Retry):
                send_email_task.delay(self.valid_config)
            mock_request.retries += 1

        with self.assertRaises(EMAIL_TRANSIENT_ERRORS[0]):
            send_email_task.delay(self.valid_config)

        self.assertEqual(len(mock_logger.warning.mock_calls), EMAIL_TASK_MAX_RETRIES)
        expected_message = (
            "Failed to send email, retrying in %s seconds. Task ID: %s; error: %s"
        )
        delay = EMAIL_TASK_BASE_RETRY_DELAY
        call_args = [c[0] for c in mock_logger.warning.call_args_list]
        self.assertEqual(
            call_args,
            [
                (expected_message, delay, 12345, mock_send_email.side_effect),
                (
                    expected_message,
                    delay * 2**1,
                    12345,
                    mock_send_email.side_effect,
                ),
                (
                    expected_message,
                    delay * 2**2,
                    12345,
                    mock_send_email.side_effect,
                ),
            ],
        )

    @patch("celery.app.task.Task.request")
    @patch("core.tasks.send_email")
    def test_unexpected_error(self, mock_send_email, mock_request):
        unexpected_error_type = ZeroDivisionError
        self.assertNotIn(unexpected_error_type, EMAIL_PERMANENT_ERRORS)
        self.assertNotIn(unexpected_error_type, EMAIL_TRANSIENT_ERRORS)

        mock_send_email.side_effect = unexpected_error_type("Unexpected error")
        mock_request.id = 12345
        mock_request.retries = 0
        mock_request.called_directly = False

        with (
            patch("core.tasks.send_email_task.retry") as mock_retry,
            self.assertRaises(unexpected_error_type),
            patch("core.tasks.logger") as mock_logger,
        ):
            mock_logger.exception = MagicMock()
            send_email_task.delay(self.valid_config)

        mock_retry.assert_not_called()
        mock_logger.exception.assert_called_once()
        log_args, log_kwargs = mock_logger.exception.call_args

        self.assertEqual(
            log_args[0], "Unexpected error while sending email. Task ID: %s"
        )
        self.assertEqual(log_args[1], mock_request.id)
