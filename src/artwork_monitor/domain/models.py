"""Hardware-independent measurement models and calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt


def calculate_gravity_deviation(
    acceleration_x_g: float | None,
    acceleration_y_g: float | None,
    acceleration_z_g: float | None,
) -> float | None:
    """Return legacy-compatible deviation from one g, not RMS vibration."""

    if None in (acceleration_x_g, acceleration_y_g, acceleration_z_g):
        return None
    magnitude_g = sqrt(
        acceleration_x_g**2 + acceleration_y_g**2 + acceleration_z_g**2
    )
    return abs(magnitude_g - 1.0)


@dataclass(frozen=True, slots=True)
class SensorReading:
    """A point-in-time sensor observation; unavailable measurements are ``None``."""

    timestamp: datetime
    temperature_c: float | None = None
    humidity_percent_rh: float | None = None
    light_lux: float | None = None
    acceleration_x_g: float | None = None
    acceleration_y_g: float | None = None
    acceleration_z_g: float | None = None
    gravity_deviation_g: float | None = None
    inclination_degrees: float | None = None

    @classmethod
    def with_calculated_gravity_deviation(
        cls,
        *,
        timestamp: datetime,
        acceleration_x_g: float | None,
        acceleration_y_g: float | None,
        acceleration_z_g: float | None,
        temperature_c: float | None = None,
        humidity_percent_rh: float | None = None,
        light_lux: float | None = None,
        inclination_degrees: float | None = None,
    ) -> "SensorReading":
        return cls(
            timestamp=timestamp,
            temperature_c=temperature_c,
            humidity_percent_rh=humidity_percent_rh,
            light_lux=light_lux,
            acceleration_x_g=acceleration_x_g,
            acceleration_y_g=acceleration_y_g,
            acceleration_z_g=acceleration_z_g,
            gravity_deviation_g=calculate_gravity_deviation(
                acceleration_x_g, acceleration_y_g, acceleration_z_g
            ),
            inclination_degrees=inclination_degrees,
        )
