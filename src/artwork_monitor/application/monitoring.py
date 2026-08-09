"""Synchronous composition of monitoring rules through hardware-neutral ports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from artwork_monitor.domain import (
    Condition,
    GPSFix,
    MonitoringThresholds,
    SensorReading,
    SessionMonitoringRecord,
    TransportSession,
    Violation,
    evaluate_reading,
)
from artwork_monitor.ports import (
    AlarmOutput,
    AlarmSource,
    GPSFixSource,
    NotificationDispatcher,
    SensorSource,
    TransportSessionRepository,
)

from .filtering import EnvironmentalFilters, clean_gravity_deviation
from .notifications import notification_messages
from .prolonged_conditions import ProlongedConditionTracker


_BUZZER_CONDITIONS = frozenset(
    {
        Condition.TEMPERATURE_LOW,
        Condition.TEMPERATURE_HIGH,
        Condition.HUMIDITY_LOW,
        Condition.HUMIDITY_HIGH,
        Condition.LIGHT_HIGH,
        Condition.GRAVITY_DEVIATION_EXCESSIVE,
    }
)


@dataclass(frozen=True, slots=True)
class MonitoringCycle:
    """The pure, structured outcome of one completed monitoring step."""

    monotonic_seconds: float
    reading: SensorReading
    gps_fix: GPSFix | None
    immediate_violations: tuple[Violation, ...]
    prolonged_violations: tuple[Violation, ...]


class MonitoringService:
    """Coordinate one deterministic transport-monitoring session at a time."""

    def __init__(
        self,
        sensor_source: SensorSource,
        *,
        gps_source: GPSFixSource | None = None,
        thresholds: MonitoringThresholds | None = None,
        session_repository: TransportSessionRepository | None = None,
        notification_dispatcher: NotificationDispatcher | None = None,
        alarm_output: AlarmOutput | None = None,
    ) -> None:
        self._sensor_source = sensor_source
        self._gps_source = gps_source
        self._thresholds = thresholds or MonitoringThresholds()
        self._filters = EnvironmentalFilters()
        self._prolonged_conditions = ProlongedConditionTracker()
        self._session_repository = session_repository
        self._notification_dispatcher = notification_dispatcher
        self._alarm_output = alarm_output
        self._session: TransportSession | None = None
        self._record_sequence = 0
        self._active = False

    def start(self, session: TransportSession | None = None) -> None:
        """Start a fresh session by resetting state and finite input sources."""

        self._filters.reset()
        self._prolonged_conditions.reset()
        self._sensor_source.reset()
        if self._gps_source is not None:
            self._gps_source.reset()
        if self._session_repository is not None:
            if session is None:
                raise ValueError(
                    "a transport session is required when persistence is enabled"
                )
            self._session_repository.create_session(session)
        if self._notification_dispatcher is not None and session is None:
            raise ValueError(
                "a transport session is required when notifications are enabled"
            )
        if (
            session is not None
            and self._session_repository is None
            and self._notification_dispatcher is None
        ):
            raise ValueError(
                "a repository or notification dispatcher is required for a transport session"
            )
        self._session = session
        self._record_sequence = 0
        self._active = True
        self._set_transport_alarm(False)

    def step(self, monotonic_seconds: float) -> MonitoringCycle | None:
        """Process one input reading, or return ``None`` when sensor input ends."""

        if not self._active:
            raise RuntimeError("start a monitoring session before taking a step")

        raw_reading = self._sensor_source.next_reading()
        if raw_reading is None:
            return None

        filtered_reading = SensorReading(
            timestamp=raw_reading.timestamp,
            temperature_c=self._filters.temperature.update(raw_reading.temperature_c),
            humidity_percent_rh=self._filters.humidity.update(
                raw_reading.humidity_percent_rh
            ),
            light_lux=self._filters.light.update(raw_reading.light_lux),
            acceleration_x_g=raw_reading.acceleration_x_g,
            acceleration_y_g=raw_reading.acceleration_y_g,
            acceleration_z_g=raw_reading.acceleration_z_g,
            gravity_deviation_g=clean_gravity_deviation(
                raw_reading.gravity_deviation_g
            ),
            inclination_degrees=raw_reading.inclination_degrees,
        )
        immediate_violations = evaluate_reading(filtered_reading, self._thresholds)
        prolonged_violations = self._prolonged_conditions.observe(
            filtered_reading,
            immediate_violations,
            monotonic_seconds,
        )
        gps_fix = self._gps_source.next_fix() if self._gps_source is not None else None
        cycle = MonitoringCycle(
            monotonic_seconds=monotonic_seconds,
            reading=filtered_reading,
            gps_fix=gps_fix,
            immediate_violations=immediate_violations,
            prolonged_violations=prolonged_violations,
        )
        if self._session_repository is not None and self._session is not None:
            self._session_repository.append_record(
                SessionMonitoringRecord(
                    session_id=self._session.session_id,
                    sequence=self._record_sequence,
                    reading=filtered_reading,
                    gps_fix=gps_fix,
                    immediate_violations=immediate_violations,
                    prolonged_violations=prolonged_violations,
                )
            )
            self._record_sequence += 1
        if self._notification_dispatcher is not None and self._session is not None:
            for message in notification_messages(
                self._session.session_id,
                immediate_violations=immediate_violations,
                prolonged_violations=prolonged_violations,
            ):
                self._notification_dispatcher.dispatch(message)
        self._set_transport_alarm(
            any(
                violation.condition in _BUZZER_CONDITIONS
                for violation in immediate_violations
            )
        )
        return cycle

    def stop(self, ended_at: datetime | None = None) -> None:
        """End the current session and clear filter and alert state."""

        self._filters.reset()
        self._prolonged_conditions.reset()
        self._set_transport_alarm(False)
        if self._session_repository is not None and self._session is not None:
            if ended_at is None:
                raise ValueError(
                    "an explicit ended_at timestamp is required when persistence is enabled"
                )
            self._session_repository.finish_session(self._session.session_id, ended_at)
        self._session = None
        self._active = False

    def _set_transport_alarm(self, active: bool) -> None:
        if self._alarm_output is not None:
            self._alarm_output.set_active(AlarmSource.TRANSPORT_MONITORING, active)
