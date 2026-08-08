"""Typed notification data, independent of a delivery mechanism."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NotificationKind(str, Enum):
    IMMEDIATE = "immediate"
    PROLONGED = "prolonged"


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """One delivery-ready description of an already-evaluated violation."""

    session_id: str
    kind: NotificationKind
    condition: str
    summary: str
    observed_value: float
    threshold_value: float
    unit: str
    occurred_at: str
