from django.db.models import F

from ..models import User


def invalidate_user_sessions(user_id: int) -> None:
    User.objects.filter(pk=user_id).update(
        session_auth_version=F("session_auth_version") + 1
    )
