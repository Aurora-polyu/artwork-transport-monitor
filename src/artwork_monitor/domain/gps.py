"""Minimal hardware-independent GPS data types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class GPSFixStatus(str, Enum):
    FIX = "fix"
    NO_FIX = "no_fix"


@dataclass(frozen=True, slots=True)
class GPSFix:
    """A scripted or observed GPS state; no-fix states have no coordinates."""

    timestamp: datetime
    status: GPSFixStatus
    latitude: float | None = None
    longitude: float | None = None

    def __post_init__(self) -> None:
        has_coordinates = self.latitude is not None and self.longitude is not None
        if self.status is GPSFixStatus.FIX and not has_coordinates:
            raise ValueError("a GPS fix requires latitude and longitude")
        if self.status is GPSFixStatus.NO_FIX and (
            self.latitude is not None or self.longitude is not None
        ):
            raise ValueError("a no-fix GPS state cannot have coordinates")

    @classmethod
    def no_fix(cls, timestamp: datetime) -> "GPSFix":
        return cls(timestamp=timestamp, status=GPSFixStatus.NO_FIX)

    @property
    def is_available(self) -> bool:
        return self.status is GPSFixStatus.FIX
