"""A tiny synchronous runner for predefined data-only simulation scenarios."""

from __future__ import annotations

from collections.abc import Sequence

from artwork_monitor.application import MonitoringCycle, MonitoringService

from .scenarios import GPSScenario, SensorScenario
from .sources import SequenceGPSFixSource, SequenceSensorSource


def run_simulated_session(
    sensor_scenario: SensorScenario,
    monotonic_seconds: Sequence[float],
    *,
    gps_scenario: GPSScenario | None = None,
) -> tuple[MonitoringCycle, ...]:
    """Run every scripted sensor reading once using supplied deterministic times."""

    if len(monotonic_seconds) < len(sensor_scenario.readings):
        raise ValueError("provide one monotonic time for every sensor reading")

    service = MonitoringService(
        SequenceSensorSource(sensor_scenario.readings),
        gps_source=SequenceGPSFixSource(gps_scenario.fixes) if gps_scenario else None,
    )
    service.start()
    results: list[MonitoringCycle] = []
    for current_time in monotonic_seconds:
        result = service.step(current_time)
        if result is None:
            break
        results.append(result)
    service.stop()
    return tuple(results)
