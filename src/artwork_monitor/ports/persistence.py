"""Storage contracts for session-scoped monitoring records."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from artwork_monitor.domain import (
    SessionMonitoringRecord,
    StoredTransportSession,
    TransportSession,
)


class TransportSessionRepository(Protocol):
    """Persist and reload one isolated transport session at a time."""

    def create_session(self, session: TransportSession) -> None: ...

    def append_record(self, record: SessionMonitoringRecord) -> None: ...

    def finish_session(self, session_id: str, ended_at: datetime) -> None: ...

    def load_session(self, session_id: str) -> StoredTransportSession: ...

    def list_session_ids(self) -> tuple[str, ...]: ...


class TransportSessionExporter(Protocol):
    """Export one already-stored session into a portable file."""

    def export(self, stored_session: StoredTransportSession) -> Path: ...
