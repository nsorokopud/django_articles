from unittest.mock import Mock, patch

from celery.exceptions import Retry
from django.db import DatabaseError
from django.test import TestCase, override_settings

from users.tasks import (
    DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY,
    delete_expired_pending_email_changes_task,
)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestDeleteExpiredPendingEmailChangesTask(TestCase):
    @patch("users.tasks.cache_lock")
    @patch("users.services.email_addresses.delete_expired_pending_email_changes")
    def test_deletes_expired_pending_email_changes(self, mock_delete, mock_cache_lock):
        mock_cache_lock.return_value.__enter__.return_value = Mock(acquired=True)
        mock_delete.return_value = 2

        delete_expired_pending_email_changes_task.apply(task_id="test-task-id")

        mock_cache_lock.assert_called_once_with(
            lock_key=DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY,
            lock_value="test-task-id",
            timeout=600,
        )
        mock_delete.assert_called_once_with()

    @patch("users.tasks.cache_lock")
    @patch("users.services.email_addresses.delete_expired_pending_email_changes")
    def test_releases_lock_when_no_rows_are_deleted(self, mock_delete, mock_cache_lock):
        mock_cache_lock.return_value.__enter__.return_value = Mock(acquired=True)
        mock_delete.return_value = 0

        delete_expired_pending_email_changes_task.apply(task_id="test-task-id")

        mock_cache_lock.assert_called_once_with(
            lock_key=DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY,
            lock_value="test-task-id",
            timeout=600,
        )
        mock_delete.assert_called_once_with()

    @patch("users.tasks.cache_lock")
    @patch("users.services.email_addresses.delete_expired_pending_email_changes")
    def test_skips_when_lock_already_exists(self, mock_delete, mock_cache_lock):
        mock_cache_lock.return_value.__enter__.return_value = Mock(acquired=False)

        delete_expired_pending_email_changes_task.apply(task_id="test-task-id")

        mock_cache_lock.assert_called_once_with(
            lock_key=DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY,
            lock_value="test-task-id",
            timeout=600,
        )
        mock_delete.assert_not_called()

    @patch("users.tasks.cache_lock")
    @patch("users.services.email_addresses.delete_expired_pending_email_changes")
    def test_releases_lock_when_delete_raises_database_error(
        self, mock_delete, mock_cache_lock
    ):
        mock_cache_lock.return_value.__enter__.return_value = Mock(acquired=True)
        mock_delete.side_effect = DatabaseError("database unavailable")

        with self.assertRaises(Retry):
            delete_expired_pending_email_changes_task.apply(
                task_id="test-task-id", throw=True
            )

        mock_cache_lock.assert_called_once_with(
            lock_key=DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY,
            lock_value="test-task-id",
            timeout=600,
        )
        mock_delete.assert_called_once_with()
        mock_cache_lock.return_value.__exit__.assert_called_once()

    @patch("users.tasks.cache_lock")
    @patch("users.services.email_addresses.delete_expired_pending_email_changes")
    def test_lock_value_falls_back_when_task_id_missing(
        self, mock_delete, mock_cache_lock
    ):
        mock_cache_lock.return_value.__enter__.return_value = Mock(acquired=True)
        mock_delete.return_value = 1

        delete_expired_pending_email_changes_task.run()

        mock_cache_lock.assert_called_once_with(
            lock_key=DELETE_PENDING_EMAIL_CHANGES_LOCK_KEY, lock_value=None, timeout=600
        )
        mock_delete.assert_called_once_with()
