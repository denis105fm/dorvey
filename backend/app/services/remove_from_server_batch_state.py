"""Redis state for batch remove-from-server: progress, pause, cancel."""

import json
from typing import Any, List, Optional

from app.core.config import settings

REDIS_KEY_PREFIX = "remove_from_server_batch:"
USER_TASKS_KEY = "user_remove_from_server_tasks:"
TTL_SEC = 86400  # 24 hours


def _redis_client():
    import redis
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_state(task_id: str) -> Optional[dict]:
    try:
        r = _redis_client()
        raw = r.get(REDIS_KEY_PREFIX + task_id)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def set_state(task_id: str, state: dict) -> None:
    try:
        r = _redis_client()
        r.setex(REDIS_KEY_PREFIX + task_id, TTL_SEC, json.dumps(state))
    except Exception:
        pass


def update_state(task_id: str, **kwargs: Any) -> None:
    s = get_state(task_id) or {}
    s.update(kwargs)
    set_state(task_id, s)


def add_user_task(user_id: int, task_id: str) -> None:
    try:
        r = _redis_client()
        r.sadd(USER_TASKS_KEY + str(user_id), task_id)
        r.expire(USER_TASKS_KEY + str(user_id), TTL_SEC)
    except Exception:
        pass


def remove_user_task(user_id: int, task_id: str) -> None:
    try:
        r = _redis_client()
        r.srem(USER_TASKS_KEY + str(user_id), task_id)
    except Exception:
        pass


def get_user_task_ids(user_id: int) -> List[str]:
    try:
        r = _redis_client()
        return list(r.smembers(USER_TASKS_KEY + str(user_id)) or [])
    except Exception:
        return []
