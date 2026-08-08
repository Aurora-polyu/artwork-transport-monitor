"""Explicit lifecycle orchestration for one deterministic transport session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from artwork_monitor.domain import StoredTransportSession, TransportSession
from artwork_monitor.ports import TransportSessionExporter, TransportSessionRepository

from .monitoring import MonitoringCycle, MonitoringService
from .reporting import SessionReport, SessionReportGenerator


class TransportSessionState(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class CompletedTransportSession:
    """Reloaded persisted artifacts and report for one completed session."""

    stored_session: StoredTransportSession
    report: SessionReport
    csv_path: Path | None
    cycles: tuple[MonitoringCycle, ...]


class TransportSessionWorkflow:
    """Coordinate one full software-only transport session without runtime threads."""

    def __init__(
        self,
        monitoring_service: MonitoringService,
        session_repository: TransportSessionRepository,
        *,
        report_generator: SessionReportGenerator | None = None,
        csv_exporter: TransportSessionExporter | None = None,
    ) -> None:
        self._monitoring_service = monitoring_service
        self._session_repository = session_repository
        self._report_generator = report_generator or SessionReportGenerator()
        self._csv_exporter = csv_exporter
        self._state = TransportSessionState.NOT_STARTED
        self._session: TransportSession | None = None
        self._cycles: list[MonitoringCycle] = []

    @property
    def state(self) -> TransportSessionState:
        return self._state

    def start(self, session: TransportSession) -> None:
        """Start a fresh session with an explicit identity and start timestamp."""

        if self._state is TransportSessionState.RUNNING:
            raise RuntimeError("cannot start a new transport session while one is running")
        self._monitoring_service.start(session)
        self._session = session
        self._cycles = []
        self._state = TransportSessionState.RUNNING

    def step(self, monotonic_seconds: float) -> MonitoringCycle | None:
        """Process one deterministic monitoring cycle during a running session."""

        self._require_running()
        cycle = self._monitoring_service.step(monotonic_seconds)
        if cycle is not None:
            self._cycles.append(cycle)
        return cycle

    def run(self, monotonic_times: tuple[float, ...]) -> tuple[MonitoringCycle, ...]:
        """Advance scripted monitoring input for supplied caller-controlled times."""

        self._require_running()
        for monotonic_seconds in monotonic_times:
            if self.step(monotonic_seconds) is None:
                break
        return tuple(self._cycles)

    def complete(self, ended_at: datetime) -> CompletedTransportSession:
        """Close, reload, export, and report exactly the running session."""

        self._require_running()
        assert self._session is not None
        self._monitoring_service.stop(ended_at)
        stored_session = self._session_repository.load_session(self._session.session_id)
        csv_path = self._csv_exporter.export(stored_session) if self._csv_exporter else None
        report = self._report_generator.generate(stored_session)
        self._state = TransportSessionState.COMPLETED
        return CompletedTransportSession(
            stored_session=stored_session,
            report=report,
            csv_path=csv_path,
            cycles=tuple(self._cycles),
        )

    def _require_running(self) -> None:
        if self._state is not TransportSessionState.RUNNING:
            raise RuntimeError("a transport session must be running for this operation")
