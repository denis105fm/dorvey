"""Redis state for batch delete: progress."""

import json
from typing import Any, Optional

from app.core.config import settings

REDIS_KEY_PREFIX = "delete_batch:"
TTL_SEC = 86400  # 24 hours


def _redis_client():
    import redis
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_state(task_id: str) -> Optional[dict]:
    """Get batch delete state (sync)."""
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
    """Set batch delete state (sync)."""
    try:
        r = _redis_client()
        key = REDIS_KEY_PREFIX + task_id
        r.setex(key, TTL_SEC, json.dumps(state))
    except Exception:
        pass


def update_state(task_id: str, **kwargs: Any) -> None:
    """Merge kwargs into existing state."""
    s = get_state(task_id) or {}
    s.update(kwargs)
    set_state(task_id, s)
