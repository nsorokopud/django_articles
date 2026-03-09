from unittest.mock import Mock, patch

from django.db import transaction
from django.test import TestCase, TransactionTestCase

from notifications.models import NotificationType
from notifications.services.dispatch import (
    DeliveryPlan,
    dispatch_notification_after_commit,
    get_delivery_plan,
)


class TestGetDeliveryPlan(TestCase):
    def test_system_enables_ws_and_email(self) -> None:
        plan = get_delivery_plan(notification_type=NotificationType.SYSTEM)
        self.assertEqual(plan, DeliveryPlan(ws=True, email=True))

    def test_non_system_enables_ws_only(self) -> None:
        plan = get_delivery_plan(notification_type=NotificationType.NEW_COMMENT)
        self.assertEqual(plan, DeliveryPlan(ws=True, email=False))


class TestDispatchNotificationAfterCommit(TransactionTestCase):
    @patch("notifications.services.dispatch.send_notification_ws_task")
    @patch("notifications.services.dispatch.send_notification_email_task")
    def test_system_schedules_ws_and_email_on_commit(
        self, mock_email_task, mock_ws_task
    ) -> None:
        ws_delay = Mock()
        email_delay = Mock()

        mock_ws_task.delay = ws_delay
        mock_email_task.delay = email_delay

        with transaction.atomic():
            dispatch_notification_after_commit(
                notification_id=1,
                notification_type=NotificationType.SYSTEM,
            )
            # Not committed yet -> should not be called
            ws_delay.assert_not_called()
            email_delay.assert_not_called()

        ws_delay.assert_called_once_with(1)
        email_delay.assert_called_once_with(1)

    @patch("notifications.services.dispatch.send_notification_ws_task")
    @patch("notifications.services.dispatch.send_notification_email_task")
    def test_non_system_schedules_ws_only_on_commit(
        self, mock_email_task, mock_ws_task
    ) -> None:
        ws_delay = Mock()
        email_delay = Mock()

        mock_ws_task.delay = ws_delay
        mock_email_task.delay = email_delay

        with transaction.atomic():
            dispatch_notification_after_commit(
                notification_id=1,
                notification_type=NotificationType.NEW_COMMENT,
            )
            ws_delay.assert_not_called()
            email_delay.assert_not_called()

        ws_delay.assert_called_once_with(1)
        email_delay.assert_not_called()

    @patch("notifications.services.dispatch.send_notification_ws_task")
    @patch("notifications.services.dispatch.send_notification_email_task")
    def test_callbacks_do_not_run_on_rollback(
        self, mock_email_task, mock_ws_task
    ) -> None:
        ws_delay = Mock()
        email_delay = Mock()

        mock_ws_task.delay = ws_delay
        mock_email_task.delay = email_delay

        try:
            with transaction.atomic():
                dispatch_notification_after_commit(
                    notification_id=1,
                    notification_type=NotificationType.SYSTEM,
                )
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass

        ws_delay.assert_not_called()
        email_delay.assert_not_called()
