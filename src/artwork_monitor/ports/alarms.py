"""Ownership-aware hardware-neutral alarm output contract."""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class AlarmSource(str, Enum):
    """Independent reasons for an audible alarm to remain active."""

    TRANSPORT_MONITORING = "transport_monitoring"
    GPS_ROUTE = "gps_route"


class AlarmOutput(Protocol):
    """Drive an alarm by source without allowing one source to silence another."""

    def set_active(self, source: AlarmSource, active: bool) -> None: ...

    def reset(self) -> None: ...
