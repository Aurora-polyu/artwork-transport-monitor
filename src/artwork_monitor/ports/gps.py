"""Hardware-neutral GPS input contract."""

from __future__ import annotations

from typing import Protocol

from artwork_monitor.domain import GPSFix


class GPSFixSource(Protocol):
    """Provide a GPS observation, or ``None`` when this pull has no new observation."""

    def next_fix(self) -> GPSFix | None: ...

    def reset(self) -> None: ...
