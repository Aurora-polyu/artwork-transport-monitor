"""Approved monitoring thresholds and pure condition evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .events import Condition, Violation
from .models import SensorReading


@dataclass(frozen=True, slots=True)
class MonitoringThresholds:
    """Environmental limits are owner-approved; motion limits remain provisional."""

    temperature_min_c: float = 18.0
    temperature_max_c: float = 27.0
    humidity_min_percent_rh: float = 25.0
    humidity_max_percent_rh: float = 75.0
    light_max_lux: float = 6000.0
    gravity_deviation_moderate_g: float = 15.0
    gravity_deviation_excessive_g: float = 20.0


def evaluate_reading(
    reading: SensorReading,
    thresholds: MonitoringThresholds | None = None,
) -> tuple[Violation, ...]:
    """Evaluate available values only; unavailable values are not violations."""

    limits = thresholds or MonitoringThresholds()
    violations: list[Violation] = []

    if reading.temperature_c is not None:
        if reading.temperature_c < limits.temperature_min_c:
            violations.append(
                _violation(
                    Condition.TEMPERATURE_LOW,
                    reading.temperature_c,
                    limits.temperature_min_c,
                    "°C",
                    reading,
                )
            )
        elif reading.temperature_c > limits.temperature_max_c:
            violations.append(
                _violation(
                    Condition.TEMPERATURE_HIGH,
                    reading.temperature_c,
                    limits.temperature_max_c,
                    "°C",
                    reading,
                )
            )

    if reading.humidity_percent_rh is not None:
        if reading.humidity_percent_rh < limits.humidity_min_percent_rh:
            violations.append(
                _violation(
                    Condition.HUMIDITY_LOW,
                    reading.humidity_percent_rh,
                    limits.humidity_min_percent_rh,
                    "%RH",
                    reading,
                )
            )
        elif reading.humidity_percent_rh > limits.humidity_max_percent_rh:
            violations.append(
                _violation(
                    Condition.HUMIDITY_HIGH,
                    reading.humidity_percent_rh,
                    limits.humidity_max_percent_rh,
                    "%RH",
                    reading,
                )
            )

    if reading.light_lux is not None and reading.light_lux > limits.light_max_lux:
        violations.append(
            _violation(
                Condition.LIGHT_HIGH,
                reading.light_lux,
                limits.light_max_lux,
                "lux",
                reading,
            )
        )

    if reading.gravity_deviation_g is not None:
        if reading.gravity_deviation_g >= limits.gravity_deviation_excessive_g:
            violations.append(
                _violation(
                    Condition.GRAVITY_DEVIATION_EXCESSIVE,
                    reading.gravity_deviation_g,
                    limits.gravity_deviation_excessive_g,
                    "g",
                    reading,
                )
            )
        elif reading.gravity_deviation_g >= limits.gravity_deviation_moderate_g:
            violations.append(
                _violation(
                    Condition.GRAVITY_DEVIATION_MODERATE,
                    reading.gravity_deviation_g,
                    limits.gravity_deviation_moderate_g,
                    "g",
                    reading,
                )
            )

    return tuple(violations)


def _violation(
    condition: Condition,
    observed_value: float,
    threshold_value: float,
    unit: str,
    reading: SensorReading,
) -> Violation:
    return Violation(
        condition=condition,
        observed_value=observed_value,
        threshold_value=threshold_value,
        unit=unit,
        occurred_at=reading.timestamp,
    )
