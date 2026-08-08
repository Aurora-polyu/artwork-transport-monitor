"""Transport-session records independent of any storage implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .events import Violation
from .gps import GPSFix
from .models import SensorReading


@dataclass(frozen=True, slots=True)
class TransportSession:
    """The business identity and wall-clock bounds of one transport session."""

    session_id: str
    started_at: datetime
    ended_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SessionMonitoringRecord:
    """One ordered cycle retained for later session-specific reporting."""

    session_id: str
    sequence: int
    reading: SensorReading
    gps_fix: GPSFix | None
    immediate_violations: tuple[Violation, ...]
    prolonged_violations: tuple[Violation, ...]


@dataclass(frozen=True, slots=True)
class StoredTransportSession:
    """A session and all of its ordered monitoring records after reload."""

    session: TransportSession
    records: tuple[SessionMonitoringRecord, ...]
