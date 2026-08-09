"""Web payload serialization shared by HTTP routes and realtime events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from artwork_monitor.domain import (
    SessionMonitoringRecord,
    StoredTransportSession,
    Violation,
    format_hong_kong_timestamp,
)


def timestamp(value: datetime) -> str:
    """Serialize one browser-visible wall-clock timestamp canonically."""

    return format_hong_kong_timestamp(value)


def violation(value: Violation) -> dict[str, Any]:
    """Serialize a stored or live violation with a canonical timestamp."""

    return {
        "condition": value.condition.value,
        "observed_value": value.observed_value,
        "threshold_value": value.threshold_value,
        "unit": value.unit,
        "occurred_at": timestamp(value.occurred_at),
    }


def monitoring_record(record: SessionMonitoringRecord) -> dict[str, Any]:
    """Expose one existing persisted monitoring record without new storage."""

    reading = record.reading
    gps_fix = record.gps_fix
    return {
        "sequence": record.sequence,
        "reading": {
            "timestamp": timestamp(reading.timestamp),
            "temperature_c": reading.temperature_c,
            "humidity_percent_rh": reading.humidity_percent_rh,
            "light_lux": reading.light_lux,
            "gravity_deviation_g": reading.gravity_deviation_g,
        },
        "gps": None
        if gps_fix is None
        else {
            "timestamp": timestamp(gps_fix.timestamp),
            "status": gps_fix.status.value,
            "latitude": gps_fix.latitude,
            "longitude": gps_fix.longitude,
        },
        "immediate_violations": [
            violation(item) for item in record.immediate_violations
        ],
        "prolonged_violations": [
            violation(item) for item in record.prolonged_violations
        ],
    }


def dashboard_session(stored: StoredTransportSession) -> dict[str, Any]:
    """Serialize exactly one persisted session for dashboard reconstruction."""

    session = stored.session
    return {
        "session_id": session.session_id,
        "started_at": timestamp(session.started_at),
        "ended_at": timestamp(session.ended_at) if session.ended_at else None,
        "records": [monitoring_record(record) for record in stored.records],
    }
