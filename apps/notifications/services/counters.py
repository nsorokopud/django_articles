from collections.abc import Iterable

from django.db import transaction
from django.db.models import Count, QuerySet

from users.models import User

from ..models import Notification


def sync_unread_notification_counts(
    *, user_ids: Iterable[int] | None = None, batch_size: int = 1000
) -> dict[str, int]:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    base_users = User.objects.all().order_by("id")
    if user_ids is not None:
        base_users = base_users.filter(id__in=list(user_ids))

    last_id = 0
    users_checked = 0
    users_updated = 0
    users_zeroed = 0

    while True:
        user_batch = _load_user_batch(
            base_users=base_users,
            last_id=last_id,
            batch_size=batch_size,
        )
        if not user_batch:
            break

        batch_user_ids = [row["id"] for row in user_batch]
        last_id = batch_user_ids[-1]
        users_checked += len(batch_user_ids)

        actual_unread_counts = _get_actual_unread_counts(batch_user_ids)
        ids_to_zero, ids_to_fix_by_count = _plan_unread_count_updates(
            user_batch=user_batch,
            actual_unread_counts=actual_unread_counts,
        )

        updated, zeroed = _apply_unread_count_updates(
            ids_to_zero=ids_to_zero,
            ids_to_fix_by_count=ids_to_fix_by_count,
        )
        users_updated += updated
        users_zeroed += zeroed

    return {
        "users_checked": users_checked,
        "users_updated": users_updated,
        "users_zeroed": users_zeroed,
    }


def _load_user_batch(
    *, base_users: QuerySet[User], last_id: int, batch_size: int
) -> list[dict[str, int]]:
    return list(
        base_users.filter(id__gt=last_id).values(
            "id",
            "unread_notifications_count",
        )[:batch_size]
    )


def _get_actual_unread_counts(batch_user_ids: list[int]) -> dict[int, int]:
    return {
        row["recipient_id"]: row["actual_unread"]
        for row in (
            Notification.objects.filter(
                recipient_id__in=batch_user_ids,
                read_at__isnull=True,
            )
            .values("recipient_id")
            .annotate(actual_unread=Count("id"))
        )
    }


def _plan_unread_count_updates(
    *,
    user_batch: list[dict[str, int]],
    actual_unread_counts: dict[int, int],
) -> tuple[list[int], dict[int, list[int]]]:
    ids_to_zero: list[int] = []
    ids_to_fix_by_count: dict[int, list[int]] = {}

    for row in user_batch:
        user_id = row["id"]
        stored = int(row["unread_notifications_count"] or 0)
        actual = actual_unread_counts.get(user_id, 0)

        if stored == actual:
            continue

        if actual == 0:
            ids_to_zero.append(user_id)
        else:
            ids_to_fix_by_count.setdefault(actual, []).append(user_id)

    return ids_to_zero, ids_to_fix_by_count


def _apply_unread_count_updates(
    *,
    ids_to_zero: list[int],
    ids_to_fix_by_count: dict[int, list[int]],
) -> tuple[int, int]:
    users_updated = 0
    users_zeroed = 0

    with transaction.atomic():
        if ids_to_zero:
            updated = (
                User.objects.filter(id__in=ids_to_zero)
                .exclude(unread_notifications_count=0)
                .update(unread_notifications_count=0)
            )
            users_updated += updated
            users_zeroed += updated

        for actual, ids in ids_to_fix_by_count.items():
            updated = (
                User.objects.filter(id__in=ids)
                .exclude(unread_notifications_count=actual)
                .update(unread_notifications_count=actual)
            )
            users_updated += updated

    return users_updated, users_zeroed
