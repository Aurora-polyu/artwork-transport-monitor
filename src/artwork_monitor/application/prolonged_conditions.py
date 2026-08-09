"""Pure injected-time tracking for prolonged environmental conditions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from artwork_monitor.domain import Condition, SensorReading, Violation


_TRACKED_CONDITIONS = (
    Condition.TEMPERATURE_LOW,
    Condition.TEMPERATURE_HIGH,
    Condition.HUMIDITY_LOW,
    Condition.HUMIDITY_HIGH,
    Condition.LIGHT_HIGH,
)


@dataclass(slots=True)
class _Episode:
    started_at: float
    alert_emitted: bool = False


class ProlongedConditionTracker:
    """Track four-second continuous episodes using caller-provided monotonic time.

    A missing measurement resets its related condition(s): without a valid
    observation, continuity cannot be established safely.
    """

    def __init__(self, duration_seconds: float = 4.0) -> None:
        if duration_seconds < 0.0:
            raise ValueError("duration_seconds must not be negative")
        self._duration_seconds = duration_seconds
        self._episodes: dict[Condition, _Episode] = {}

    def observe(
        self,
        reading: SensorReading,
        violations: Iterable[Violation],
        monotonic_seconds: float,
    ) -> tuple[Violation, ...]:
        """Return each tracked violation exactly once when its episode is ready."""

        violations_by_condition = {
            violation.condition: violation
            for violation in violations
            if violation.condition in _TRACKED_CONDITIONS
        }
        valid_conditions = _valid_conditions(reading)
        ready: list[Violation] = []

        for condition in _TRACKED_CONDITIONS:
            violation = violations_by_condition.get(condition)
            if violation is None:
                self._episodes.pop(condition, None)
                continue
            if condition not in valid_conditions:
                self._episodes.pop(condition, None)
                continue

            episode = self._episodes.setdefault(condition, _Episode(monotonic_seconds))
            if (
                not episode.alert_emitted
                and monotonic_seconds - episode.started_at >= self._duration_seconds
            ):
                episode.alert_emitted = True
                ready.append(violation)

        return tuple(ready)

    def reset(self) -> None:
        """Clear all episode state at a future transport-session boundary."""

        self._episodes.clear()


def _valid_conditions(reading: SensorReading) -> set[Condition]:
    conditions: set[Condition] = set()
    if reading.temperature_c is not None:
        conditions.update((Condition.TEMPERATURE_LOW, Condition.TEMPERATURE_HIGH))
    if reading.humidity_percent_rh is not None:
        conditions.update((Condition.HUMIDITY_LOW, Condition.HUMIDITY_HIGH))
    if reading.light_lux is not None:
        conditions.add(Condition.LIGHT_HIGH)
    return conditions
