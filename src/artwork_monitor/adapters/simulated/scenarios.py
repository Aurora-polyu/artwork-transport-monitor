"""Small reusable, deterministic data-only scenarios for future integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from artwork_monitor.domain import GPSFix, GPSFixStatus, SensorReading


@dataclass(frozen=True, slots=True)
class SensorScenario:
    name: str
    readings: tuple[SensorReading, ...]


@dataclass(frozen=True, slots=True)
class GPSScenario:
    name: str
    fixes: tuple[GPSFix, ...]


_START = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def normal_transport() -> SensorScenario:
    return SensorScenario(
        "normal_transport",
        (
            _reading(temperature_c=22.0, humidity_percent_rh=50.0, light_lux=500.0),
            _reading(offset_seconds=1, temperature_c=22.2, humidity_percent_rh=50.5, light_lux=520.0),
        ),
    )


def excessive_temperature() -> SensorScenario:
    return SensorScenario("excessive_temperature", (_reading(temperature_c=27.1),))


def high_humidity() -> SensorScenario:
    return SensorScenario("high_humidity", (_reading(humidity_percent_rh=75.1),))


def excessive_light() -> SensorScenario:
    return SensorScenario("excessive_light", (_reading(light_lux=6000.1),))


def multiple_environmental_violations() -> SensorScenario:
    return SensorScenario(
        "multiple_environmental_violations",
        (_reading(temperature_c=17.9, humidity_percent_rh=75.1, light_lux=6000.1),),
    )


def missing_sensor_reading() -> SensorScenario:
    return SensorScenario(
        "missing_sensor_reading",
        (_reading(temperature_c=None, humidity_percent_rh=None, light_lux=None),),
    )


def gravity_deviation_example() -> SensorScenario:
    return SensorScenario(
        "gravity_deviation_example",
        (_reading(acceleration_x_g=0.0, acceleration_y_g=0.0, acceleration_z_g=1.2, gravity_deviation_g=0.2),),
    )


def dark_environment_with_acceleration() -> SensorScenario:
    return SensorScenario(
        "dark_environment_with_acceleration",
        (_reading(light_lux=0.0, acceleration_x_g=0.0, acceleration_y_g=0.0, acceleration_z_g=1.2, gravity_deviation_g=0.2),),
    )


def gps_route() -> GPSScenario:
    return GPSScenario(
        "gps_route",
        (
            _fix(22.3020, 114.1770),
            _fix(22.3030, 114.1780, offset_seconds=1),
            _fix(22.3040, 114.1790, offset_seconds=2),
        ),
    )


def gps_dropout() -> GPSScenario:
    return GPSScenario(
        "gps_dropout",
        (
            _fix(22.3020, 114.1770),
            GPSFix.no_fix(_START + timedelta(seconds=1)),
            _fix(22.3040, 114.1790, offset_seconds=2),
        ),
    )


def _reading(
    *,
    offset_seconds: int = 0,
    temperature_c: float | None = 22.0,
    humidity_percent_rh: float | None = 50.0,
    light_lux: float | None = 500.0,
    acceleration_x_g: float | None = 0.0,
    acceleration_y_g: float | None = 0.0,
    acceleration_z_g: float | None = 1.0,
    gravity_deviation_g: float | None = 0.0,
) -> SensorReading:
    return SensorReading(
        timestamp=_START + timedelta(seconds=offset_seconds),
        temperature_c=temperature_c,
        humidity_percent_rh=humidity_percent_rh,
        light_lux=light_lux,
        acceleration_x_g=acceleration_x_g,
        acceleration_y_g=acceleration_y_g,
        acceleration_z_g=acceleration_z_g,
        gravity_deviation_g=gravity_deviation_g,
    )


def _fix(latitude: float, longitude: float, *, offset_seconds: int = 0) -> GPSFix:
    return GPSFix(
        timestamp=_START + timedelta(seconds=offset_seconds),
        status=GPSFixStatus.FIX,
        latitude=latitude,
        longitude=longitude,
    )
