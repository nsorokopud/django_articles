import threading
from unittest import skipUnless
from unittest.mock import patch

from django.db import OperationalError, close_old_connections, connection, transaction
from django.test import TransactionTestCase

from notifications.models import Notification, NotificationType
from notifications.services import actions, counters
from users.models import User


POSTGRES_LOCK_NOT_AVAILABLE_SQLSTATE = "55P03"


@skipUnless(
    connection.vendor == "postgresql",
    "Concurrency test requires PostgreSQL row-level locking.",
)
class TestSyncUnreadNotificationCountsConcurrency(TransactionTestCase):
    def test_unread_count_sync_blocks_while_mark_read_holds_user_row_lock(self) -> None:
        user = User.objects.create_user(
            username="user", email="user@test.com", unread_notifications_count=1
        )
        notification = Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.SYSTEM,
            level=Notification.Level.INFO,
            title="Unread notification",
            body="Body",
            payload={},
            dedupe_key="",
            read_at=None,
        )

        mark_read_paused_after_user_update = threading.Event()
        allow_mark_read_to_finish = threading.Event()
        worker_errors = []

        def mark_read_worker() -> None:
            # Ensure this thread uses a separate thread-local DB connection
            close_old_connections()

            try:
                actions.mark_notification_as_read(notification.id, user.id)
            except BaseException as e:  # pylint: disable=W0718
                # Surface worker exceptions in the main test thread
                worker_errors.append(e)
            finally:
                connection.close()

        original_decrement_unread = actions._decrement_unread

        def decrement_unread_then_wait(user_id: int) -> None:
            original_decrement_unread(user_id)

            # The User counter UPDATE has completed, but mark_notification_as_read()'s
            # atomic transaction remains open.
            # PostgreSQL holds a lock on the User row until the transaction commits.
            mark_read_paused_after_user_update.set()

            if not allow_mark_read_to_finish.wait(timeout=5):
                raise TimeoutError(
                    "Timed out waiting for the test thread to let "
                    "mark_notification_as_read finish"
                )

        with patch.object(actions, "_decrement_unread", new=decrement_unread_then_wait):
            mark_read_thread = threading.Thread(target=mark_read_worker, daemon=True)
            mark_read_thread.start()

            try:
                self.assertTrue(
                    mark_read_paused_after_user_update.wait(timeout=5),
                    "mark_notification_as_read did not reach the pause after updating "
                    "the User row",
                )

                # Sync tries to acquire a conflicting lock on the same User row.
                # Because mark-as-read has not committed, PostgreSQL waits for that
                # transaction. lock_timeout converts the wait into OperationalError.
                with self.assertRaises(OperationalError) as lock_error:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout = '500ms'")

                        counters.sync_unread_notification_counts(
                            user_ids=[user.id], batch_size=1
                        )

                database_error = lock_error.exception.__cause__
                sqlstate = getattr(database_error, "sqlstate", None) or getattr(
                    database_error, "pgcode", None
                )
                self.assertEqual(sqlstate, POSTGRES_LOCK_NOT_AVAILABLE_SQLSTATE)
            finally:
                # Let the worker finish and commit its transaction even if an
                # assertion above fails
                allow_mark_read_to_finish.set()
                mark_read_thread.join(timeout=5)

        self.assertFalse(
            mark_read_thread.is_alive(),
            "mark_notification_as_read thread did not finish",
        )

        if worker_errors:
            raise worker_errors[0]

        notification.refresh_from_db()
        user.refresh_from_db()

        self.assertIsNotNone(notification.read_at)
        self.assertEqual(user.unread_notifications_count, 0)

        actual_count = Notification.objects.filter(
            recipient_id=user.id, read_at__isnull=True
        ).count()
        self.assertEqual(user.unread_notifications_count, actual_count)
