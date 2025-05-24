def get_subscribers_count_cache_key(user_id: int) -> str:
    return f"users:subscribers_count:{user_id}"
