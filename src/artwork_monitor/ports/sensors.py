"""Hardware-neutral sensor input contract."""

from __future__ import annotations

from typing import Protocol

from artwork_monitor.domain import SensorReading


class SensorSource(Protocol):
    """Provide the next logical sensor reading, or ``None`` when exhausted."""

    def next_reading(self) -> SensorReading | None: ...

    def reset(self) -> None: ...
