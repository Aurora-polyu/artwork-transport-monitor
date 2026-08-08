"""Deterministic persistence conversions shared by standard-library adapters."""

from __future__ import annotations

import json
from datetime import datetime

from artwork_monitor.domain import Condition, Violation, format_hong_kong_timestamp


def timestamp_to_hong_kong_iso(timestamp: datetime) -> str:
    """Compatibility wrapper for the canonical domain timestamp formatter."""

    return format_hong_kong_timestamp(timestamp)


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
