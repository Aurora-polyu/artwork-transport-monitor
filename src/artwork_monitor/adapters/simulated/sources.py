"""Simple deterministic adapters that only provide predefined input data."""

from __future__ import annotations

from collections.abc import Iterable

from artwork_monitor.domain import GPSFix, SensorReading


class SequenceSensorSource:
    """Return a finite sequence of readings; ``None`` signals exhaustion."""

    def __init__(self, readings: Iterable[SensorReading]) -> None:
        self._readings = tuple(readings)
        self._position = 0

    def next_reading(self) -> SensorReading | None:
        if self._position >= len(self._readings):
            return None
        reading = self._readings[self._position]
        self._position += 1
        return reading

    def reset(self) -> None:
        self._position = 0


class SequenceGPSFixSource:
    """Return a finite sequence of GPS states; ``None`` signals exhaustion."""

    def __init__(self, fixes: Iterable[GPSFix]) -> None:
        self._fixes = tuple(fixes)
        self._position = 0

    def next_fix(self) -> GPSFix | None:
        if self._position >= len(self._fixes):
            return None
        fix = self._fixes[self._position]
        self._position += 1
        return fix

    def reset(self) -> None:
        self._position = 0
