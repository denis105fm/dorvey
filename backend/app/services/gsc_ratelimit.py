"""GSC indexing rate limit. Max ~200 URLs per user per hour."""
from datetime import datetime, timedelta
from typing import Optional

# In-memory fallback (use Redis in production)
_gsc_submissions: dict[int, list[datetime]] = {}


def check_gsc_limit(user_id: int, max_per_hour: int = 200) -> tuple[bool, int]:
    """
    Check if user can submit. Returns (allowed, remaining).
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=1)
    if user_id not in _gsc_submissions:
        _gsc_submissions[user_id] = []
    times = [t for t in _gsc_submissions[user_id] if t > cutoff]
    _gsc_submissions[user_id] = times
    count = len(times)
    if count >= max_per_hour:
        return False, 0
    return True, max_per_hour - count


def record_gsc_submission(user_id: int) -> None:
    _gsc_submissions.setdefault(user_id, []).append(datetime.utcnow())
