from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from notifications.tasks import (
    NOTIFICATIONS_CLEANUP_LOCK_KEY,
    cleanup_old_read_notifications_task,
    send_notification_email_task,
    send_notification_ws_task,
)


class TestSendNotificationWSTask(SimpleTestCase):
    @patch("notifications.tasks.async_to_sync")
    @patch("notifications.services.delivery_ws.send_ws_notification")
    def test_calls_send_ws_notification_via_async_to_sync(
        self, mock_send_ws_notification, mock_async_to_sync
    ):
        sync_callable = Mock()
        mock_async_to_sync.return_value = sync_callable

        send_notification_ws_task.run(notification_id=123)

        mock_async_to_sync.assert_called_once_with(mock_send_ws_notification)
        sync_callable.assert_called_once_with(123)

    @patch("notifications.tasks.async_to_sync")
    @patch("notifications.tasks.logger.exception")
    def test_logs_exception_when_ws_delivery_raises(
        self, mock_log_exception, mock_async_to_sync
    ):
        sync_callable = Mock(side_effect=RuntimeError("error"))
        mock_async_to_sync.return_value = sync_callable

        send_notification_ws_task.run(notification_id=456)

        sync_callable.assert_called_once_with(456)
        mock_log_exception.assert_called_once_with(
            "WS delivery failed (notification_id=%s)", 456
        )


class TestSendNotificationEmailTask(SimpleTestCase):
    def test_returns_when_config_missing(self):
        with (
            patch(
                "notifications.tasks.build_notification_email_config",
                return_value=None,
            ) as mock_build,
            patch("notifications.tasks.EmailConfig.from_dict") as mock_from_dict,
            patch("notifications.tasks.send_email") as mock_send_email,
        ):
            send_notification_email_task.run(notification_id=1)

            mock_build.assert_called_once_with(1)
            mock_from_dict.assert_not_called()
            mock_send_email.assert_not_called()

    def test_sends_email_when_config_present(self):
        cfg_dict = {
            "recipients": ["x@test.com"],
            "subject": "T",
            "text_content": "B",
        }
        cfg_obj = Mock(name="EmailConfig")

        with (
            patch(
                "notifications.tasks.build_notification_email_config",
                return_value=cfg_dict,
            ) as mock_build,
            patch(
                "notifications.tasks.EmailConfig.from_dict",
                return_value=cfg_obj,
            ) as mock_from_dict,
            patch("notifications.tasks.send_email") as mock_send_email,
        ):
            send_notification_email_task.run(notification_id=99)

            mock_build.assert_called_once_with(99)
            mock_from_dict.assert_called_once_with(cfg_dict)
            mock_send_email.assert_called_once_with(cfg_obj)

    def test_raises_when_email_config_from_dict_fails(self):
        with (
            patch(
                "notifications.tasks.build_notification_email_config",
                return_value={"x": 1},
            ),
            patch(
                "notifications.tasks.EmailConfig.from_dict",
                side_effect=ValueError("error"),
            ),
        ):
            with self.assertRaises(ValueError):
                send_notification_email_task.run(notification_id=1)


@override_settings(NOTIFICATIONS_CLEANUP_LOCK_TTL_SECONDS=60)
class TestCleanupOldReadNotificationsTask(SimpleTestCase):
    @patch("notifications.tasks.cache.delete")
    @patch("notifications.services.retention.cleanup_old_read_notifications")
    @patch("notifications.tasks.cache.add")
    def test_runs_cleanup_when_lock_acquired(
        self,
        mock_cache_add,
        mock_cleanup_old_read_notifications,
        mock_cache_delete,
    ):
        mock_cache_add.return_value = True
        mock_cleanup_old_read_notifications.return_value = 7

        result = cleanup_old_read_notifications_task()

        self.assertEqual(result, 7)
        mock_cache_add.assert_called_once_with(
            NOTIFICATIONS_CLEANUP_LOCK_KEY,
            "1",
            timeout=60,
        )
        mock_cleanup_old_read_notifications.assert_called_once_with()
        mock_cache_delete.assert_called_once_with(NOTIFICATIONS_CLEANUP_LOCK_KEY)

    @patch("notifications.tasks.logger.info")
    @patch("notifications.tasks.cache.delete")
    @patch("notifications.services.retention.cleanup_old_read_notifications")
    @patch("notifications.tasks.cache.add")
    def test_skips_when_lock_not_acquired(
        self,
        mock_cache_add,
        mock_cleanup_old_read_notifications,
        mock_cache_delete,
        mock_logger_info,
    ):
        mock_cache_add.return_value = False

        result = cleanup_old_read_notifications_task()

        self.assertEqual(result, 0)
        mock_cache_add.assert_called_once_with(
            NOTIFICATIONS_CLEANUP_LOCK_KEY,
            "1",
            timeout=60,
        )
        mock_cleanup_old_read_notifications.assert_not_called()
        mock_cache_delete.assert_not_called()
        mock_logger_info.assert_called_once_with(
            "Notification cleanup skipped: already running"
        )

    @patch("notifications.tasks.cache.delete")
    @patch("notifications.services.retention.cleanup_old_read_notifications")
    @patch("notifications.tasks.cache.add")
    def test_deletes_lock_when_cleanup_raises(
        self,
        mock_cache_add,
        mock_cleanup_old_read_notifications,
        mock_cache_delete,
    ):
        mock_cache_add.return_value = True
        mock_cleanup_old_read_notifications.side_effect = RuntimeError("error")

        with self.assertRaises(RuntimeError):
            cleanup_old_read_notifications_task()

        mock_cache_add.assert_called_once_with(
            NOTIFICATIONS_CLEANUP_LOCK_KEY,
            "1",
            timeout=60,
        )
        mock_cleanup_old_read_notifications.assert_called_once_with()
        mock_cache_delete.assert_called_once_with(NOTIFICATIONS_CLEANUP_LOCK_KEY)
