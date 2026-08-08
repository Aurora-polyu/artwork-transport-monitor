"""Deterministic persistence conversions shared by standard-library adapters."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from artwork_monitor.domain import Condition, Violation


HONG_KONG = ZoneInfo("Asia/Hong_Kong")


def timestamp_to_hong_kong_iso(timestamp: datetime) -> str:
    """Normalize an aware wall-clock timestamp to explicit Asia/Hong_Kong ISO 8601."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("persisted timestamps must be timezone-aware")
    return timestamp.astimezone(HONG_KONG).isoformat()


def violations_to_json(violations: tuple[Violation, ...]) -> str:
    payload = [
        {
            "condition": violation.condition.value,
            "observed_value": violation.observed_value,
            "occurred_at": timestamp_to_hong_kong_iso(violation.occurred_at),
            "threshold_value": violation.threshold_value,
            "unit": violation.unit,
        }
        for violation in violations
    ]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def violations_from_json(value: str) -> tuple[Violation, ...]:
    return tuple(
        Violation(
            condition=Condition(item["condition"]),
            observed_value=item["observed_value"],
            threshold_value=item["threshold_value"],
            unit=item["unit"],
            occurred_at=datetime.fromisoformat(item["occurred_at"]),
        )
        for item in json.loads(value)
    )
