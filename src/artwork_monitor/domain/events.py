"""Typed condition outcomes suitable for later storage, alerts, and reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Condition(str, Enum):
    TEMPERATURE_LOW = "temperature_low"
    TEMPERATURE_HIGH = "temperature_high"
    HUMIDITY_LOW = "humidity_low"
    HUMIDITY_HIGH = "humidity_high"
    LIGHT_HIGH = "light_high"
    GRAVITY_DEVIATION_MODERATE = "gravity_deviation_moderate"
    GRAVITY_DEVIATION_EXCESSIVE = "gravity_deviation_excessive"


@dataclass(frozen=True, slots=True)
class Violation:
    """A deterministic result of evaluating one reading against one condition."""

    condition: Condition
    observed_value: float
    threshold_value: float
    unit: str
    occurred_at: datetime
