"""Redis state for batch deploy: progress, pause, cancel."""

import json
from typing import List, Optional

from app.core.config import settings

REDIS_KEY_PREFIX = "deploy_batch:"
USER_TASKS_KEY = "user_deploy_tasks:"  # + user_id
TTL_SEC = 86400  # 24 hours


def _redis_client():
    import redis
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_state(task_id: str) -> Optional[dict]:
    """Get batch deploy state (sync, for Celery worker and API via thread)."""
    try:
        r = _redis_client()
        key = REDIS_KEY_PREFIX + task_id
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def set_state(task_id: str, state: dict) -> None:
    """Set batch deploy state (sync)."""
    try:
        r = _redis_client()
        key = REDIS_KEY_PREFIX + task_id
        r.setex(key, TTL_SEC, json.dumps(state))
    except Exception:
        pass


def update_state(task_id: str, **kwargs) -> None:
    """Merge kwargs into existing state."""
    s = get_state(task_id) or {}
    s.update(kwargs)
    set_state(task_id, s)


def add_user_task(user_id: int, task_id: str) -> None:
    """Register task as active for user (any device can see it)."""
    try:
        r = _redis_client()
        key = USER_TASKS_KEY + str(user_id)
        r.sadd(key, task_id)
        r.expire(key, TTL_SEC)
    except Exception:
        pass


def remove_user_task(user_id: int, task_id: str) -> None:
    """Unregister task when completed/cancelled."""
    try:
        r = _redis_client()
        r.srem(USER_TASKS_KEY + str(user_id), task_id)
    except Exception:
        pass


def get_user_task_ids(user_id: int) -> List[str]:
    """Return list of active deploy task ids for user."""
    try:
        r = _redis_client()
        key = USER_TASKS_KEY + str(user_id)
        return list(r.smembers(key) or [])
    except Exception:
        return []
