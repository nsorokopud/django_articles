from django.db import IntegrityError


def get_constraint_name(exc: IntegrityError) -> str | None:
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    diagnostics = getattr(cause, "diag", None)
    return getattr(diagnostics, "constraint_name", None)
