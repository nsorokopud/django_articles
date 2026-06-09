import json


def parse_liked_payload(request) -> bool | None:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None

    liked = payload.get("liked")

    if not isinstance(liked, bool):
        return None

    return liked
