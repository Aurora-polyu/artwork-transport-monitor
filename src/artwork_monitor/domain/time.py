"""Canonical wall-clock timestamp formatting for application records."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


HONG_KONG = ZoneInfo("Asia/Hong_Kong")


def format_hong_kong_timestamp(timestamp: datetime) -> str:
    """Return an aware timestamp as ISO 8601 in Asia/Hong_Kong (+08:00)."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("canonical timestamps must be timezone-aware")
    return timestamp.astimezone(HONG_KONG).isoformat()
